import asyncio
import time
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Conversation, LLMRun, Message
from app.db.session import get_db_session
from app.schemas.conversations import (
    ConversationDetailResponse,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.answering import (
    AnswerResult,
    RetrievalEmptyError,
    finalize_answer_citations,
    generate_answer,
    prepare_answer,
)
from app.services.chunking import count_query_tokens
from app.services.llm import OllamaUnavailableError, stream_ollama
from app.services.sse import sse_event

router = APIRouter(prefix="/conversations", tags=["conversations"])

_HISTORY_WINDOW = 10


def _utcnow() -> datetime:
    return datetime.now(UTC)


@router.post("", response_model=ConversationResponse, status_code=201)
async def create_conversation(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationResponse:
    conv_id = uuid.uuid4()
    created = _utcnow()
    db.add(Conversation(id=conv_id, created_at=created, updated_at=created))
    await db.commit()
    return ConversationResponse(conversation_id=str(conv_id), created_at=created)


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationDetailResponse:
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    return ConversationDetailResponse(
        conversation_id=str(conversation.id),
        created_at=conversation.created_at,
        messages=[
            MessageResponse(
                message_id=str(m.id),
                role=m.role,
                content=m.content,
                created_at=m.created_at,
            )
            for m in messages
        ],
    )


@router.post("/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SendMessageResponse:
    settings = get_settings()

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty or whitespace.")

    token_count = count_query_tokens(body.message)
    if token_count > settings.max_query_tokens:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Message is too long. Maximum allowed query length is "
                f"{settings.max_query_tokens} tokens."
            ),
        )

    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    # Load recent history before storing the current user message
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_WINDOW)
    )
    recent = list(reversed(history_result.scalars().all()))
    history = [{"role": m.role, "content": m.content} for m in recent]

    # Persist user message (IDs generated in Python for testability)
    db.add(Message(
        id=uuid.uuid4(),
        conversation_id=conversation_id,
        role="user",
        content=body.message,
        created_at=_utcnow(),
    ))

    result: AnswerResult | None = None
    llm_status = "failed"
    llm_error: str | None = None
    http_exc: HTTPException | None = None

    try:
        result = await generate_answer(
            question=body.message,
            k=body.k,
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout_seconds,
            history=history,
        )
        llm_status = "success"
    except RetrievalEmptyError as exc:
        llm_error = str(exc)
        http_exc = HTTPException(status_code=404, detail="No relevant chunks found.")
    except OllamaUnavailableError as exc:
        llm_error = str(exc)
        http_exc = HTTPException(status_code=503, detail=f"Ollama is unavailable: {exc}")
    except RuntimeError as exc:
        llm_error = str(exc)
        http_exc = HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        llm_error = str(exc)
        http_exc = HTTPException(status_code=500, detail="Unexpected error during answer generation.")

    # Persist assistant message on success
    assistant_msg_id: uuid.UUID | None = None
    if result is not None:
        assistant_msg_id = uuid.uuid4()
        db.add(Message(
            id=assistant_msg_id,
            conversation_id=conversation_id,
            role="assistant",
            content=result.answer,
            created_at=_utcnow(),
        ))

    # Always log the LLM run, linked to this conversation
    db.add(LLMRun(
        conversation_id=conversation_id,
        provider="ollama",
        model_name=settings.ollama_model,
        prompt=result.prompt if result else None,
        response=result.answer if result else None,
        status=llm_status,
        error_message=llm_error,
        latency_ms=result.latency_ms if result else None,
        run_metadata={
            "question": body.message,
            "k": body.k,
            "source_chunk_ids": [s.chunk_id for s in result.sources] if result else [],
            "source_document_ids": [s.document_id for s in result.sources] if result else [],
            "citations": [
                {"source_number": c.source_number, "chunk_id": c.chunk_id, "filename": c.filename}
                for c in result.citations
            ] if result else [],
        },
    ))

    try:
        await db.commit()
    except Exception:
        pass

    if http_exc:
        raise http_exc

    return SendMessageResponse(
        conversation_id=str(conversation_id),
        message_id=str(assistant_msg_id),
        answer=result.answer,
        citations=result.citations,
        sources=result.sources,
    )


@router.post("/{conversation_id}/messages/stream")
async def stream_message(
    conversation_id: uuid.UUID,
    body: SendMessageRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    settings = get_settings()
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty or whitespace.")
    if count_query_tokens(body.message) > settings.max_query_tokens:
        raise HTTPException(
            status_code=422,
            detail=f"Message is too long. Maximum allowed query length is {settings.max_query_tokens} tokens.",
        )
    conversation = await db.get(Conversation, conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(_HISTORY_WINDOW)
    )
    recent = list(reversed(history_result.scalars().all()))
    history = [{"role": message.role, "content": message.content} for message in recent]
    try:
        prompt, sources, citations = prepare_answer(body.message, body.k, history=history)
    except RetrievalEmptyError as exc:
        raise HTTPException(status_code=404, detail="No relevant chunks found.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    db.add(
        Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role="user",
            content=body.message,
            created_at=_utcnow(),
        )
    )
    conversation.updated_at = _utcnow()
    await db.commit()

    async def events():
        answer_parts: list[str] = []
        status = "failed"
        error_message: str | None = None
        usage: dict[str, int | None] = {"prompt_tokens": None, "output_tokens": None}
        assistant_id: uuid.UUID | None = None
        started = time.monotonic()
        yield sse_event(
            "sources",
            {
                "sources": [source.model_dump() for source in sources],
            },
        )
        try:
            async for event in stream_ollama(
                prompt,
                settings.ollama_model,
                settings.ollama_base_url,
                settings.ollama_timeout_seconds,
            ):
                if event["type"] == "token":
                    answer_parts.append(event["text"])
                    yield sse_event("token", {"text": event["text"]})
                elif event["type"] == "complete":
                    usage = {
                        "prompt_tokens": event.get("prompt_tokens"),
                        "output_tokens": event.get("output_tokens"),
                    }

            assistant_id = uuid.uuid4()
            answer_text = "".join(answer_parts)
            answer_text, answer_citations = finalize_answer_citations(
                answer_text, citations
            )
            streamed_text = "".join(answer_parts)
            if answer_text != streamed_text:
                suffix = answer_text[len(streamed_text) :]
                answer_parts.append(suffix)
                yield sse_event("token", {"text": suffix})
            db.add(
                Message(
                    id=assistant_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer_text,
                    created_at=_utcnow(),
                )
            )
            try:
                await db.commit()
            except Exception:
                await db.rollback()
                raise
            status = "success"
            yield sse_event(
                "complete",
                {
                    "conversation_id": str(conversation_id),
                    "message_id": str(assistant_id),
                    "answer": answer_text,
                    "citations": [
                        citation.model_dump() for citation in answer_citations
                    ],
                    "sources": [source.model_dump() for source in sources],
                    "model": settings.ollama_model,
                    "usage": usage,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                },
            )
        except asyncio.CancelledError:
            status = "cancelled"
            error_message = "Client disconnected."
            await db.rollback()
            raise
        except Exception as exc:
            status = "failed"
            error_message = str(exc)
            await db.rollback()
            yield sse_event("error", {"detail": error_message})
        finally:
            db.add(
                LLMRun(
                    conversation_id=conversation_id,
                    provider="ollama",
                    model_name=settings.ollama_model,
                    prompt=prompt,
                    response="".join(answer_parts) or None,
                    input_tokens=usage["prompt_tokens"],
                    output_tokens=usage["output_tokens"],
                    status=status,
                    error_message=error_message,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    run_metadata={
                        "question": body.message,
                        "k": body.k,
                        "streamed": True,
                        "source_chunk_ids": [source.chunk_id for source in sources],
                    },
                )
            )
            try:
                await db.commit()
            except Exception:
                await db.rollback()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
