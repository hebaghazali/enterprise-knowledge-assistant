import asyncio
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import LLMRun
from app.db.session import get_db_session
from app.schemas.answering import AnswerRequest, AnswerResponse
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

router = APIRouter(tags=["answer"])


@router.post("/answer", response_model=AnswerResponse)
async def answer(
    body: AnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AnswerResponse:
    settings = get_settings()

    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty or whitespace.")

    token_count = count_query_tokens(body.question)
    if token_count > settings.max_query_tokens:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Question is too long. Maximum allowed query length is "
                f"{settings.max_query_tokens} tokens."
            ),
        )

    result: AnswerResult | None = None
    llm_status = "failed"
    llm_error: str | None = None
    http_exc: HTTPException | None = None

    try:
        result = await generate_answer(
            question=body.question,
            k=body.k,
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout_seconds,
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

    llm_run = LLMRun(
        provider="ollama",
        model_name=settings.ollama_model,
        prompt=result.prompt if result else None,
        response=result.answer if result else None,
        status=llm_status,
        error_message=llm_error,
        latency_ms=result.latency_ms if result else None,
        run_metadata={
            "question": body.question,
            "k": body.k,
            "source_chunk_ids": [s.chunk_id for s in result.sources] if result else [],
            "source_document_ids": [s.document_id for s in result.sources] if result else [],
            "citations": [
                {"source_number": c.source_number, "chunk_id": c.chunk_id, "filename": c.filename}
                for c in result.citations
            ] if result else [],
        },
    )
    db.add(llm_run)
    try:
        await db.commit()
    except Exception:
        pass

    if http_exc:
        raise http_exc

    return AnswerResponse(
        question=body.question,
        answer=result.answer,
        citations=result.citations,
        sources=result.sources,
        model=settings.ollama_model,
        k=body.k,
    )


@router.post("/answer/stream")
async def answer_stream(
    body: AnswerRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    settings = get_settings()
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question must not be empty or whitespace.")
    if count_query_tokens(body.question) > settings.max_query_tokens:
        raise HTTPException(
            status_code=422,
            detail=f"Question is too long. Maximum allowed query length is {settings.max_query_tokens} tokens.",
        )
    try:
        prompt, sources, citations = prepare_answer(body.question, body.k)
    except RetrievalEmptyError as exc:
        raise HTTPException(status_code=404, detail="No relevant chunks found.") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def events():
        run_id = uuid.uuid4()
        answer_parts: list[str] = []
        status = "failed"
        error_message: str | None = None
        usage: dict[str, int | None] = {"prompt_tokens": None, "output_tokens": None}
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
            status = "success"
            answer_text = "".join(answer_parts)
            answer_text, answer_citations = finalize_answer_citations(
                answer_text, citations
            )
            streamed_text = "".join(answer_parts)
            if answer_text != streamed_text:
                suffix = answer_text[len(streamed_text) :]
                answer_parts.append(suffix)
                yield sse_event("token", {"text": suffix})
            yield sse_event(
                "complete",
                {
                    "llm_run_id": str(run_id),
                    "question": body.question,
                    "answer": answer_text,
                    "citations": [
                        citation.model_dump() for citation in answer_citations
                    ],
                    "sources": [source.model_dump() for source in sources],
                    "model": settings.ollama_model,
                    "k": body.k,
                    "usage": usage,
                    "latency_ms": int((time.monotonic() - started) * 1000),
                },
            )
        except asyncio.CancelledError:
            status = "cancelled"
            error_message = "Client disconnected."
            raise
        except Exception as exc:
            error_message = str(exc)
            yield sse_event("error", {"detail": error_message})
        finally:
            db.add(
                LLMRun(
                    id=run_id,
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
                        "question": body.question,
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
