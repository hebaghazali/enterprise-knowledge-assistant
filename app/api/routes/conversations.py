import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
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
from app.services.answering import AnswerResult, RetrievalEmptyError, generate_answer
from app.services.chunking import count_query_tokens
from app.services.llm import OllamaUnavailableError

router = APIRouter(prefix="/conversations", tags=["conversations"])

_HISTORY_WINDOW = 10


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        sources=result.sources,
    )
