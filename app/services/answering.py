import time
from dataclasses import dataclass

from app.schemas.answering import AnswerSourceResponse, CitationResponse
from app.services.llm import call_ollama
from app.services.prompting import build_prompt
from app.services.retrieval import retrieve

_SOURCE_PREVIEW_LENGTH = 200
_CITATION_PREVIEW_LENGTH = 300


class RetrievalEmptyError(RuntimeError):
    pass


@dataclass
class AnswerResult:
    answer: str
    prompt: str
    sources: list[AnswerSourceResponse]
    citations: list[CitationResponse]
    latency_ms: int


async def generate_answer(
    question: str,
    k: int,
    model: str,
    base_url: str,
    timeout: int,
    history: list[dict[str, str]] | None = None,
) -> AnswerResult:
    chunks = retrieve(question, k)

    if not chunks:
        raise RetrievalEmptyError("No relevant chunks found for the given question.")

    prompt = build_prompt(question, chunks, history=history)

    start = time.monotonic()
    answer_text = await call_ollama(prompt, model, base_url, timeout)
    latency_ms = int((time.monotonic() - start) * 1000)

    sources = [
        AnswerSourceResponse(
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            filename=c.filename,
            chunk_index=c.chunk_index,
            similarity_score=c.similarity_score,
            content_preview=c.content[:_SOURCE_PREVIEW_LENGTH],
        )
        for c in chunks
    ]

    citations = [
        CitationResponse(
            source_number=i,
            chunk_id=c.chunk_id,
            document_id=c.document_id,
            filename=c.filename,
            chunk_index=c.chunk_index,
            similarity_score=c.similarity_score,
            content_preview=c.content[:_CITATION_PREVIEW_LENGTH],
        )
        for i, c in enumerate(chunks, start=1)
    ]

    return AnswerResult(
        answer=answer_text,
        prompt=prompt,
        sources=sources,
        citations=citations,
        latency_ms=latency_ms,
    )
