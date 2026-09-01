import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.db.models import Document
from app.db.session import get_db_session
from app.main import app
from app.schemas.answering import AnswerSourceResponse, CitationResponse
from app.services.llm import OllamaUnavailableError, get_ollama_info, stream_ollama
from app.services.vector_store import chroma_health, delete_chunks_by_document

client = TestClient(app)


def _db_override(db: AsyncMock):
    async def override():
        yield db

    return override


def test_delete_chunks_by_document_uses_metadata_filter():
    collection = MagicMock()
    chroma_client = MagicMock()
    chroma_client.get_or_create_collection.return_value = collection

    with patch("app.services.vector_store._make_client", return_value=chroma_client):
        delete_chunks_by_document("chunks", "document-1")

    collection.delete.assert_called_once_with(where={"document_id": "document-1"})


def test_chroma_health_returns_heartbeat():
    chroma_client = MagicMock()
    chroma_client.heartbeat.return_value = 42
    with patch("app.services.vector_store._make_client", return_value=chroma_client):
        assert chroma_health() == {"status": "ok", "heartbeat": 42}


async def test_ollama_info_reports_missing_configured_model():
    tags = MagicMock(status_code=200)
    tags.json.return_value = {"models": [{"name": "llama3.2:3b"}]}
    version = MagicMock(status_code=200)
    version.json.return_value = {"version": "1.0.0"}
    http_client = AsyncMock()
    http_client.__aenter__.return_value = http_client
    http_client.get.side_effect = [tags, version]

    with patch("app.services.llm.httpx.AsyncClient", return_value=http_client):
        result = await get_ollama_info("http://ollama:11434", "llama3.1:8b")

    assert result["status"] == "degraded"
    assert result["configured_model_present"] is False
    assert result["models"] == ["llama3.2:3b"]


async def test_stream_ollama_yields_tokens_and_usage():
    class Response:
        status_code = 200

        async def aiter_lines(self):
            for line in (
                '{"response":"Hello ","done":false}',
                '{"response":"world","done":false}',
                '{"response":"","done":true,"prompt_eval_count":8,"eval_count":2}',
            ):
                yield line

    stream_context = AsyncMock()
    stream_context.__aenter__.return_value = Response()
    http_client = AsyncMock()
    http_client.__aenter__.return_value = http_client
    http_client.stream = MagicMock(return_value=stream_context)

    with patch("app.services.llm.httpx.AsyncClient", return_value=http_client):
        events = [
            event
            async for event in stream_ollama(
                "prompt", "llama3.1:8b", "http://ollama:11434", 30
            )
        ]

    assert [event["text"] for event in events[:2]] == ["Hello ", "world"]
    assert events[-1] == {
        "type": "complete",
        "prompt_tokens": 8,
        "output_tokens": 2,
    }


async def test_stream_ollama_rejects_an_incomplete_stream():
    class Response:
        status_code = 200

        async def aiter_lines(self):
            yield '{"response":"partial","done":false}'

    stream_context = AsyncMock()
    stream_context.__aenter__.return_value = Response()
    http_client = AsyncMock()
    http_client.__aenter__.return_value = http_client
    http_client.stream = MagicMock(return_value=stream_context)

    with (
        patch("app.services.llm.httpx.AsyncClient", return_value=http_client),
        pytest.raises(OllamaUnavailableError, match="before completion"),
    ):
        _ = [
            event
            async for event in stream_ollama(
                "prompt", "llama3.1:8b", "http://ollama:11434", 30
            )
        ]


def test_readiness_returns_503_with_dependency_details():
    db = AsyncMock()
    app.dependency_overrides[get_db_session] = _db_override(db)
    try:
        with (
            patch(
                "app.api.routes.health._database_status",
                new=AsyncMock(return_value={"status": "ok"}),
            ),
            patch(
                "app.api.routes.health._chroma_status",
                new=AsyncMock(return_value={"status": "ok"}),
            ),
            patch(
                "app.api.routes.health._ollama_status",
                new=AsyncMock(return_value={"status": "error", "detail": "offline"}),
            ),
        ):
            response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"]["services"]["ollama"]["detail"] == "offline"


def test_process_document_creates_queued_job():
    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        filename="handbook.txt",
        source_type="upload",
        status="uploaded",
        chunk_count=0,
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.get.return_value = document
    active_result = MagicMock()
    active_result.scalar_one_or_none.return_value = None
    db.execute.return_value = active_result
    app.dependency_overrides[get_db_session] = _db_override(db)
    try:
        response = client.post(f"/documents/{document_id}/process")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert document.status == "queued"


def test_process_document_maps_concurrent_insert_to_conflict():
    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        filename="handbook.txt",
        source_type="upload",
        status="uploaded",
        chunk_count=0,
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.get.return_value = document
    active_result = MagicMock()
    active_result.scalar_one_or_none.return_value = None
    db.execute.return_value = active_result
    db.commit.side_effect = IntegrityError("INSERT", {}, Exception("duplicate"))
    app.dependency_overrides[get_db_session] = _db_override(db)
    try:
        response = client.post(f"/documents/{document_id}/process")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    db.rollback.assert_awaited_once()


def test_delete_document_removes_all_managed_resources():
    document_id = uuid.uuid4()
    document = Document(
        id=document_id,
        filename="handbook.txt",
        source_type="upload",
        status="vector_indexed",
        chunk_count=1,
        document_metadata={},
    )
    db = AsyncMock()
    db.get.return_value = document
    app.dependency_overrides[get_db_session] = _db_override(db)
    try:
        with patch("app.api.routes.documents.delete_chunks_by_document") as cleanup:
            response = client.delete(f"/documents/{document_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    cleanup.assert_called_once()
    db.delete.assert_awaited_once_with(document)


def test_answer_stream_orders_sources_tokens_and_completion():
    source = AnswerSourceResponse(
        chunk_id="chunk-1",
        document_id="doc-1",
        filename="handbook.txt",
        chunk_index=0,
        similarity_score=0.9,
        content_preview="Remote work is allowed.",
    )
    citation = CitationResponse(source_number=1, **source.model_dump())

    async def fake_stream(*args, **kwargs):
        yield {"type": "token", "text": "Remote "}
        yield {"type": "token", "text": "work."}
        yield {"type": "complete", "prompt_tokens": 10, "output_tokens": 2}

    db = AsyncMock()
    db.add = MagicMock()
    app.dependency_overrides[get_db_session] = _db_override(db)
    try:
        with (
            patch("app.api.routes.answer.count_query_tokens", return_value=3),
            patch(
                "app.api.routes.answer.prepare_answer",
                return_value=("prompt", [source], [citation]),
            ),
            patch("app.api.routes.answer.stream_ollama", new=fake_stream),
        ):
            response = client.post(
                "/answer/stream", json={"question": "Remote work?", "k": 1}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text.index("event: sources") < response.text.index("event: token")
    assert response.text.index("event: token") < response.text.index("event: complete")
    assert '"answer": "Remote work."' in response.text
    db.commit.assert_awaited()
