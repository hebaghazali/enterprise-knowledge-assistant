from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import LLMRun
from app.db.session import get_db_session
from app.schemas.answering import AnswerRequest, AnswerResponse
from app.services.answering import AnswerResult, RetrievalEmptyError, generate_answer
from app.services.chunking import count_query_tokens
from app.services.llm import OllamaUnavailableError

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
        sources=result.sources,
        model=settings.ollama_model,
        k=body.k,
    )
