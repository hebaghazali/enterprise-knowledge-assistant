import re
import time
from dataclasses import dataclass

from app.core.config import get_settings
from app.schemas.answering import AnswerSourceResponse, CitationResponse
from app.schemas.retrieval import SearchResultResponse
from app.services.llm import call_ollama
from app.services.prompting import build_prompt
from app.services.retrieval import retrieve

_SOURCE_PREVIEW_LENGTH = 200
_CITATION_PREVIEW_LENGTH = 300
_SOURCE_REFERENCE_PATTERN = re.compile(r"\[Source\s+(\d+)\]", re.IGNORECASE)


class RetrievalEmptyError(RuntimeError):
    pass


@dataclass
class AnswerResult:
    answer: str
    prompt: str
    sources: list[AnswerSourceResponse]
    citations: list[CitationResponse]
    latency_ms: int


def citations_for_answer(
    answer: str, candidates: list[CitationResponse]
) -> list[CitationResponse]:
    """Return citation metadata only for source numbers used in the answer."""
    referenced = {
        int(match.group(1)) for match in _SOURCE_REFERENCE_PATTERN.finditer(answer)
    }
    return [
        citation
        for citation in candidates
        if citation.source_number in referenced
    ]


def finalize_answer_citations(
    answer: str, candidates: list[CitationResponse]
) -> tuple[str, list[CitationResponse]]:
    """Ensure a supported single-source answer has an explicit citation."""
    citations = citations_for_answer(answer, candidates)
    normalized = answer.casefold()
    is_refusal = any(
        marker in normalized
        for marker in ("don't know", "do not know", "not in the provided documents")
    )
    if not citations and len(candidates) == 1 and not is_refusal:
        citation = candidates[0]
        answer = f"{answer.rstrip()} [Source {citation.source_number}]"
        citations = [citation]
    return answer, citations


def select_answer_chunks(
    chunks: list[SearchResultResponse], score_margin: float
) -> list[SearchResultResponse]:
    """Keep candidates whose score is close to the best retrieved match."""
    if not chunks:
        return []
    best_score = chunks[0].similarity_score
    cutoff = best_score - max(score_margin, 0.0)
    return [chunk for chunk in chunks if chunk.similarity_score >= cutoff]


def prepare_answer(
    question: str,
    k: int,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, list[AnswerSourceResponse], list[CitationResponse]]:
    chunks = retrieve(question, k)
    chunks = select_answer_chunks(
        chunks, get_settings().answer_relevance_score_margin
    )
    if not chunks:
        raise RetrievalEmptyError("No relevant chunks found for the given question.")

    prompt = build_prompt(question, chunks, history=history)
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
    return prompt, sources, citations


async def generate_answer(
    question: str,
    k: int,
    model: str,
    base_url: str,
    timeout: int,
    history: list[dict[str, str]] | None = None,
) -> AnswerResult:
    prompt, sources, citations = prepare_answer(question, k, history=history)

    start = time.monotonic()
    answer_text = await call_ollama(prompt, model, base_url, timeout)
    latency_ms = int((time.monotonic() - start) * 1000)
    answer_text, citations = finalize_answer_citations(answer_text, citations)

    return AnswerResult(
        answer=answer_text,
        prompt=prompt,
        sources=sources,
        citations=citations,
        latency_ms=latency_ms,
    )
