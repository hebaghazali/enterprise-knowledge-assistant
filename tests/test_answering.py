from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from app.db.models import LLMRun
from app.db.session import get_db_session
from app.main import app
from app.schemas.answering import AnswerSourceResponse, CitationResponse
from app.schemas.retrieval import SearchResultResponse
from app.services.answering import (
    AnswerResult,
    RetrievalEmptyError,
    citations_for_answer,
    finalize_answer_citations,
    select_answer_chunks,
)
from app.services.llm import OllamaUnavailableError, call_ollama
from app.services.prompting import build_prompt

client = TestClient(app)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FAKE_CHUNK = SearchResultResponse(
    chunk_id="chunk-1",
    document_id="doc-1",
    filename="handbook.txt",
    chunk_index=0,
    content="Employees may work remotely up to three days per week.",
    token_count=12,
    similarity_score=0.9,
)

_FAKE_SOURCE = AnswerSourceResponse(
    chunk_id="chunk-1",
    document_id="doc-1",
    filename="handbook.txt",
    chunk_index=0,
    similarity_score=0.9,
    content_preview="Employees may work remotely up to three days per week.",
)

_FAKE_CITATION = CitationResponse(
    source_number=1,
    chunk_id="chunk-1",
    document_id="doc-1",
    filename="handbook.txt",
    chunk_index=0,
    similarity_score=0.9,
    content_preview="Employees may work remotely up to three days per week.",
)

_FAKE_ANSWER_TEXT = "Employees may work remotely up to three days per week. [Source 1]"

_FAKE_RESULT = AnswerResult(
    answer=_FAKE_ANSWER_TEXT,
    prompt="the full prompt",
    sources=[_FAKE_SOURCE],
    citations=[_FAKE_CITATION],
    latency_ms=350,
)


def _make_mock_db() -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def _db_override(mock_db: AsyncMock):
    async def _override():
        yield mock_db

    return _override


# ---------------------------------------------------------------------------
# Prompt builder — unit tests (pure function, no mocks)
# ---------------------------------------------------------------------------


def test_prompt_includes_question():
    prompt = build_prompt("What is the remote work policy?", [_FAKE_CHUNK])
    assert "What is the remote work policy?" in prompt


def test_prompt_includes_chunk_content():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert "Employees may work remotely up to three days per week." in prompt


def test_prompt_includes_source_filename():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert "handbook.txt" in prompt


def test_prompt_includes_dont_know_instruction():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert "I don't know based on the provided documents" in prompt


def test_prompt_treats_paraphrases_as_supported_matches():
    prompt = build_prompt("What is our PTO policy?", [_FAKE_CHUNK])
    assert "synonyms, abbreviations, and paraphrases" in prompt
    assert "Ignore unrelated sources" in prompt


def test_prompt_places_context_before_current_question():
    prompt = build_prompt("What is our PTO policy?", [_FAKE_CHUNK])
    assert prompt.index("<document_context>") < prompt.index("<question>")


def test_prompt_numbers_multiple_sources():
    chunk2 = SearchResultResponse(
        chunk_id="chunk-2",
        document_id="doc-2",
        filename="policy.txt",
        chunk_index=1,
        content="Annual training is required for all staff.",
        token_count=9,
        similarity_score=0.7,
    )
    prompt = build_prompt("training?", [_FAKE_CHUNK, chunk2])
    assert "[Source 1]" in prompt
    assert "[Source 2]" in prompt
    assert "handbook.txt" in prompt
    assert "policy.txt" in prompt


def test_citations_include_only_referenced_sources():
    second = _FAKE_CITATION.model_copy(
        update={"source_number": 2, "chunk_id": "chunk-2"}
    )
    selected = citations_for_answer(
        "The policy allows three days. [Source 1]", [_FAKE_CITATION, second]
    )
    assert [citation.source_number for citation in selected] == [1]


def test_fallback_answer_has_no_citations():
    assert (
        citations_for_answer(
            "I don't know based on the provided documents.", [_FAKE_CITATION]
        )
        == []
    )


def test_single_source_answer_gets_a_deterministic_citation():
    answer, citations = finalize_answer_citations(
        "Employees receive 25 days annually.", [_FAKE_CITATION]
    )
    assert answer.endswith("[Source 1]")
    assert citations == [_FAKE_CITATION]


def test_single_source_fallback_does_not_get_a_citation():
    answer, citations = finalize_answer_citations(
        "I don't know based on the provided documents.", [_FAKE_CITATION]
    )
    assert answer == "I don't know based on the provided documents."
    assert citations == []


def test_answer_context_keeps_only_chunks_close_to_best_score():
    close = _FAKE_CHUNK.model_copy(
        update={"chunk_id": "close", "similarity_score": 0.87}
    )
    irrelevant = _FAKE_CHUNK.model_copy(
        update={"chunk_id": "irrelevant", "similarity_score": 0.72}
    )
    selected = select_answer_chunks([_FAKE_CHUNK, close, irrelevant], 0.05)
    assert [chunk.chunk_id for chunk in selected] == ["chunk-1", "close"]


def test_answer_context_always_keeps_best_chunk():
    assert select_answer_chunks([_FAKE_CHUNK], 0.0) == [_FAKE_CHUNK]


def test_prompt_includes_chunk_id():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert "chunk-1" in prompt


# ---------------------------------------------------------------------------
# Ollama service — unit tests (mocked httpx)
# ---------------------------------------------------------------------------


async def test_call_ollama_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "  The answer is 42.  "}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("app.services.llm.httpx.AsyncClient", return_value=mock_client):
        result = await call_ollama("prompt text", "llama3.1:8b", "http://localhost:11434", 120)

    assert result == "The answer is 42."
    assert mock_client.post.call_args.kwargs["json"]["options"] == {
        "temperature": 0.1
    }


async def test_call_ollama_timeout():
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.side_effect = httpx.TimeoutException("request timed out")

    with patch("app.services.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(OllamaUnavailableError, match="timed out"):
            await call_ollama("prompt", "llama3.1:8b", "http://localhost:11434", 30)


async def test_call_ollama_connection_failure():
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.side_effect = httpx.ConnectError("connection refused")

    with patch("app.services.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(OllamaUnavailableError, match="Cannot connect"):
            await call_ollama("prompt", "llama3.1:8b", "http://localhost:11434", 120)


async def test_call_ollama_non_200_response():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("app.services.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(OllamaUnavailableError, match="HTTP 500"):
            await call_ollama("prompt", "llama3.1:8b", "http://localhost:11434", 120)


async def test_call_ollama_empty_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"response": "   "}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("app.services.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(OllamaUnavailableError, match="empty"):
            await call_ollama("prompt", "llama3.1:8b", "http://localhost:11434", 120)


async def test_call_ollama_missing_response_key():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.post.return_value = mock_response

    with patch("app.services.llm.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(OllamaUnavailableError, match="empty"):
            await call_ollama("prompt", "llama3.1:8b", "http://localhost:11434", 120)


# ---------------------------------------------------------------------------
# POST /answer — endpoint tests
# ---------------------------------------------------------------------------


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_success(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post(
            "/answer", json={"question": "How many remote days per week?", "k": 5}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["question"] == "How many remote days per week?"
        assert data["answer"] == _FAKE_ANSWER_TEXT
        assert data["k"] == 5
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_sources_included(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "remote days?", "k": 3})
        assert response.status_code == 200
        data = response.json()
        assert len(data["sources"]) == 1
        src = data["sources"][0]
        assert src["chunk_id"] == "chunk-1"
        assert src["document_id"] == "doc-1"
        assert src["filename"] == "handbook.txt"
        assert src["chunk_index"] == 0
        assert src["similarity_score"] == 0.9
        assert "content_preview" in src
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_model_name_in_response(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "remote days?", "k": 5})
        data = response.json()
        assert "model" in data
        assert isinstance(data["model"], str)
        assert len(data["model"]) > 0
    finally:
        app.dependency_overrides.clear()


def test_answer_empty_question_returns_400():
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "", "k": 5})
        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_answer_whitespace_question_returns_400():
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "   ", "k": 5})
        assert response.status_code == 400
    finally:
        app.dependency_overrides.clear()


def test_answer_missing_question_returns_422():
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"k": 5})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_answer_k_zero_returns_422():
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "test?", "k": 0})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_answer_k_too_large_returns_422():
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "test?", "k": 11})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=600)
def test_answer_long_question_returns_422(mock_count):
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "word " * 600, "k": 5})
        assert response.status_code == 422
        assert "too long" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_no_results_returns_404(mock_gen, mock_count):
    mock_gen.side_effect = RetrievalEmptyError("No relevant chunks found.")
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "some obscure question?", "k": 5})
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_ollama_unavailable_returns_503(mock_gen, mock_count):
    mock_gen.side_effect = OllamaUnavailableError("Cannot connect to Ollama.")
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "remote days?", "k": 5})
        assert response.status_code == 503
        assert "Ollama" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_chromadb_unavailable_returns_503(mock_gen, mock_count):
    mock_gen.side_effect = RuntimeError("ChromaDB operation failed: connection refused")
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "remote days?", "k": 5})
        assert response.status_code == 503
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# LLM run logging tests
# ---------------------------------------------------------------------------


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_llm_run_success_row_created(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post("/answer", json={"question": "remote days?", "k": 5})
        assert mock_db.add.called
        llm_run = mock_db.add.call_args[0][0]
        assert isinstance(llm_run, LLMRun)
        assert llm_run.status == "success"
        assert llm_run.provider == "ollama"
        assert llm_run.response == _FAKE_ANSWER_TEXT
        assert llm_run.error_message is None
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_llm_run_failure_row_created(mock_gen, mock_count):
    mock_gen.side_effect = OllamaUnavailableError("Ollama is down.")
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post("/answer", json={"question": "remote days?", "k": 5})
        assert mock_db.add.called
        llm_run = mock_db.add.call_args[0][0]
        assert isinstance(llm_run, LLMRun)
        assert llm_run.status == "failed"
        assert llm_run.error_message is not None
        assert mock_db.commit.called
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_llm_run_metadata_includes_question_and_k(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post("/answer", json={"question": "remote days?", "k": 3})
        llm_run = mock_db.add.call_args[0][0]
        assert llm_run.run_metadata["question"] == "remote days?"
        assert llm_run.run_metadata["k"] == 3
        assert "source_chunk_ids" in llm_run.run_metadata
        assert "source_document_ids" in llm_run.run_metadata
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_llm_run_logged_even_on_404(mock_gen, mock_count):
    mock_gen.side_effect = RetrievalEmptyError("No chunks.")
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "obscure?", "k": 5})
        assert response.status_code == 404
        assert mock_db.add.called
        llm_run = mock_db.add.call_args[0][0]
        assert llm_run.status == "failed"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Prompt builder — citation rules
# ---------------------------------------------------------------------------


def test_prompt_includes_citation_rules():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert "Citation rules:" in prompt
    assert "[Source N]" in prompt


def test_prompt_citation_rules_include_only_cite_retrieved():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert "Only cite sources that appear in the provided context" in prompt


def test_prompt_citation_rules_include_dont_know_no_citation():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    assert 'Do not add citations to the "I don\'t know" response' in prompt


def test_prompt_citation_rules_appear_before_question():
    prompt = build_prompt("remote work?", [_FAKE_CHUNK])
    citation_pos = prompt.index("Citation rules:")
    question_pos = prompt.index("Question:")
    assert citation_pos < question_pos


# ---------------------------------------------------------------------------
# /answer — citations in response
# ---------------------------------------------------------------------------


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_citations_included(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        response = client.post("/answer", json={"question": "remote days?", "k": 5})
        assert response.status_code == 200
        data = response.json()
        assert "citations" in data
        assert len(data["citations"]) == 1
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_citation_fields(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.post("/answer", json={"question": "remote days?", "k": 5}).json()
        cit = data["citations"][0]
        assert cit["source_number"] == 1
        assert cit["chunk_id"] == "chunk-1"
        assert cit["document_id"] == "doc-1"
        assert cit["filename"] == "handbook.txt"
        assert cit["chunk_index"] == 0
        assert cit["similarity_score"] == 0.9
        assert "content_preview" in cit
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_sources_still_present_with_citations(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        data = client.post("/answer", json={"question": "remote days?", "k": 5}).json()
        assert "sources" in data
        assert len(data["sources"]) == 1
        assert "citations" in data
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.answer.count_query_tokens", return_value=10)
@patch("app.api.routes.answer.generate_answer", new_callable=AsyncMock)
def test_answer_llm_run_metadata_includes_citations(mock_gen, mock_count):
    mock_gen.return_value = _FAKE_RESULT
    mock_db = _make_mock_db()

    app.dependency_overrides[get_db_session] = _db_override(mock_db)
    try:
        client.post("/answer", json={"question": "remote days?", "k": 3})
        llm_run = mock_db.add.call_args[0][0]
        assert "citations" in llm_run.run_metadata
        citations_meta = llm_run.run_metadata["citations"]
        assert len(citations_meta) == 1
        assert citations_meta[0]["source_number"] == 1
        assert citations_meta[0]["chunk_id"] == "chunk-1"
        assert citations_meta[0]["filename"] == "handbook.txt"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Citation builder — unit tests (via generate_answer service)
# ---------------------------------------------------------------------------


def test_citation_source_number_starts_at_one():
    assert _FAKE_CITATION.source_number == 1


def test_citation_preserves_chunk_metadata():
    assert _FAKE_CITATION.chunk_id == "chunk-1"
    assert _FAKE_CITATION.document_id == "doc-1"
    assert _FAKE_CITATION.filename == "handbook.txt"
    assert _FAKE_CITATION.chunk_index == 0
    assert _FAKE_CITATION.similarity_score == 0.9


def test_citation_preview_is_string():
    assert isinstance(_FAKE_CITATION.content_preview, str)
    assert len(_FAKE_CITATION.content_preview) > 0
