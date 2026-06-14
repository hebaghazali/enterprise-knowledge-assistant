import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.db.models import Document, DocumentChunk
from app.db.session import get_db_session
from app.main import app
from app.services.embeddings import embed_text, embed_texts

client = TestClient(app)

_NOW = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_doc(status: str = "chunked") -> Document:
    doc = Document(
        filename="test.txt",
        content_type="text/plain",
        source_type="upload",
        status=status,
        chunk_count=2,
        document_metadata={
            "original_filename": "test.txt",
            "saved_path": "storage/uploads/fake.txt",
            "file_size_bytes": 100,
            "text_length": 100,
            "extension": ".txt",
        },
    )
    doc.id = uuid.uuid4()
    doc.created_at = _NOW
    doc.updated_at = _NOW
    return doc


def _make_chunk(doc_id: uuid.UUID, index: int, content: str) -> DocumentChunk:
    chunk = DocumentChunk(
        document_id=doc_id,
        chunk_index=index,
        content=content,
        token_count=len(content.split()),
    )
    chunk.id = uuid.uuid4()
    chunk.created_at = _NOW
    return chunk


def _index_db_override(doc: Document, chunks: list[DocumentChunk]):
    """DB override for POST /{document_id}/index (two execute calls: doc + chunks)."""

    async def _override():
        session = MagicMock()

        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = doc

        mock_chunks_result = MagicMock()
        mock_chunks_result.scalars.return_value.all.return_value = chunks

        session.execute = AsyncMock(side_effect=[mock_doc_result, mock_chunks_result])
        session.commit = AsyncMock()
        yield session

    return _override


def _not_found_db_override():
    """DB override that returns None for the document lookup."""

    async def _override():
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        yield session

    return _override


# ---------------------------------------------------------------------------
# Embedding service — unit tests (model is mocked; no download required)
# ---------------------------------------------------------------------------


def test_embed_text_returns_list_of_floats():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch("app.services.embeddings._get_model", return_value=mock_model):
        result = embed_text("hello world")

    assert isinstance(result, list)
    assert all(isinstance(v, float) for v in result)


def test_embed_text_not_numpy_array():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])

    with patch("app.services.embeddings._get_model", return_value=mock_model):
        result = embed_text("hello world")

    # Must be a plain Python list, not a numpy array.
    assert type(result) is list


def test_embed_texts_count_matches_input():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.random.rand(3, 384).astype(np.float32)

    with patch("app.services.embeddings._get_model", return_value=mock_model):
        result = embed_texts(["a", "b", "c"])

    assert len(result) == 3
    assert all(isinstance(row, list) for row in result)


def test_embed_texts_each_row_is_list_of_floats():
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1, 0.2], [0.3, 0.4]])

    with patch("app.services.embeddings._get_model", return_value=mock_model):
        result = embed_texts(["hello", "world"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


# ---------------------------------------------------------------------------
# Vector store — unit tests (chromadb is mocked; no live Chroma required)
# ---------------------------------------------------------------------------


def test_upsert_chunks_calls_collection_upsert():
    from app.services.vector_store import upsert_chunks

    with patch("app.services.vector_store._make_client") as mock_make_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_make_client.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        upsert_chunks(
            collection_name="test_col",
            ids=["id-1", "id-2"],
            documents=["text one", "text two"],
            embeddings=[[0.1, 0.2], [0.3, 0.4]],
            metadatas=[{"chunk_index": 0}, {"chunk_index": 1}],
        )

    mock_client.get_or_create_collection.assert_called_once_with(name="test_col")
    mock_collection.upsert.assert_called_once_with(
        ids=["id-1", "id-2"],
        documents=["text one", "text two"],
        embeddings=[[0.1, 0.2], [0.3, 0.4]],
        metadatas=[{"chunk_index": 0}, {"chunk_index": 1}],
    )


def test_upsert_chunks_raises_runtime_error_on_chroma_failure():
    from app.services.vector_store import upsert_chunks

    with patch("app.services.vector_store._make_client") as mock_make_client:
        mock_make_client.side_effect = ConnectionRefusedError("refused")

        with pytest.raises(RuntimeError, match="ChromaDB operation failed"):
            upsert_chunks(
                collection_name="test_col",
                ids=["id-1"],
                documents=["text"],
                embeddings=[[0.1]],
                metadatas=[{}],
            )


def test_upsert_chunks_uses_correct_ids_and_metadata():
    from app.services.vector_store import upsert_chunks

    captured = {}

    def fake_upsert(**kwargs):
        captured.update(kwargs)

    with patch("app.services.vector_store._make_client") as mock_make_client:
        mock_client = MagicMock()
        mock_collection = MagicMock()
        mock_collection.upsert.side_effect = fake_upsert
        mock_make_client.return_value = mock_client
        mock_client.get_or_create_collection.return_value = mock_collection

        upsert_chunks(
            collection_name="col",
            ids=["chunk-uuid-1"],
            documents=["hello world"],
            embeddings=[[0.5, 0.5]],
            metadatas=[{"document_id": "doc-uuid", "chunk_index": 0}],
        )

    assert captured["ids"] == ["chunk-uuid-1"]
    assert captured["metadatas"][0]["document_id"] == "doc-uuid"
    assert captured["metadatas"][0]["chunk_index"] == 0


# ---------------------------------------------------------------------------
# POST /documents/{document_id}/index — endpoint tests
# ---------------------------------------------------------------------------

_FAKE_EMBEDDINGS = [[0.1] * 384, [0.2] * 384]


def test_index_document_not_found():
    app.dependency_overrides[get_db_session] = _not_found_db_override()
    try:
        response = client.post(f"/documents/{uuid.uuid4()}/index")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


def test_index_document_no_chunks():
    doc = _make_doc(status="uploaded")

    app.dependency_overrides[get_db_session] = _index_db_override(doc, [])
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 400
        assert "chunk" in response.json()["detail"].lower()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.upsert_chunks")
@patch("app.api.routes.documents.embed_texts", return_value=_FAKE_EMBEDDINGS)
def test_index_document_success(mock_embed, mock_upsert):
    doc = _make_doc()
    chunks = [
        _make_chunk(doc.id, 0, "hello world"),
        _make_chunk(doc.id, 1, "foo bar baz"),
    ]

    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "vector_indexed"
        assert data["chunk_count"] == 2
        assert data["indexed_chunk_count"] == 2
        assert data["skipped_chunk_count"] == 0
        assert data["embedding_model"] == "sentence-transformers/all-MiniLM-L6-v2"
        assert data["chroma_collection"] == "enterprise_knowledge_chunks"
        assert data["document_id"] == str(doc.id)
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.upsert_chunks")
@patch("app.api.routes.documents.embed_texts", return_value=_FAKE_EMBEDDINGS)
def test_index_document_embed_texts_called_with_chunk_contents(mock_embed, mock_upsert):
    doc = _make_doc()
    chunks = [
        _make_chunk(doc.id, 0, "hello world"),
        _make_chunk(doc.id, 1, "foo bar"),
    ]

    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        client.post(f"/documents/{doc.id}/index")
        mock_embed.assert_called_once_with(["hello world", "foo bar"])
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.upsert_chunks")
@patch("app.api.routes.documents.embed_texts", return_value=_FAKE_EMBEDDINGS)
def test_index_document_upsert_called_with_chunk_uuids(mock_embed, mock_upsert):
    doc = _make_doc()
    chunks = [
        _make_chunk(doc.id, 0, "hello"),
        _make_chunk(doc.id, 1, "world"),
    ]
    expected_ids = [str(c.id) for c in chunks]

    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        client.post(f"/documents/{doc.id}/index")
        call_kwargs = mock_upsert.call_args.kwargs
        assert call_kwargs["ids"] == expected_ids
        assert call_kwargs["collection_name"] == "enterprise_knowledge_chunks"
        meta = call_kwargs["metadatas"]
        assert meta[0]["chunk_index"] == 0
        assert meta[1]["chunk_index"] == 1
        assert meta[0]["filename"] == "test.txt"
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.embed_texts", return_value=[[0.1] * 384])
@patch(
    "app.api.routes.documents.upsert_chunks",
    side_effect=RuntimeError("ChromaDB operation failed: connection refused"),
)
def test_index_document_chroma_unavailable(mock_upsert, mock_embed):
    doc = _make_doc()
    chunks = [_make_chunk(doc.id, 0, "hello")]

    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 503
        assert "ChromaDB" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.upsert_chunks")
@patch("app.api.routes.documents.embed_texts", return_value=_FAKE_EMBEDDINGS)
def test_index_document_idempotent(mock_embed, mock_upsert):
    """First call indexes all chunks; second call skips all (chroma_id already set)."""
    doc = _make_doc()
    chunks = [
        _make_chunk(doc.id, 0, "hello world"),
        _make_chunk(doc.id, 1, "foo bar baz"),
    ]

    # First call — all chunks are new.
    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 200
        data = response.json()
        assert data["indexed_chunk_count"] == 2
        assert data["skipped_chunk_count"] == 0
        mock_embed.assert_called_once()
        mock_upsert.assert_called_once()
    finally:
        app.dependency_overrides.clear()

    mock_embed.reset_mock()
    mock_upsert.reset_mock()

    # Second call — chunks now have chroma_id set (mutated in-place by first call).
    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "vector_indexed"
        assert data["indexed_chunk_count"] == 0
        assert data["skipped_chunk_count"] == 2
        mock_embed.assert_not_called()
        mock_upsert.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.upsert_chunks")
@patch("app.api.routes.documents.embed_texts")
def test_index_document_all_skipped(mock_embed, mock_upsert):
    """All chunks already indexed → embed and upsert not called; status still vector_indexed."""
    doc = _make_doc()
    chunks = [
        _make_chunk(doc.id, 0, "hello world"),
        _make_chunk(doc.id, 1, "foo bar baz"),
    ]
    for chunk in chunks:
        chunk.chroma_id = str(chunk.id)
        chunk.chroma_collection = "enterprise_knowledge_chunks"

    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "vector_indexed"
        assert data["chunk_count"] == 2
        assert data["indexed_chunk_count"] == 0
        assert data["skipped_chunk_count"] == 2
        mock_embed.assert_not_called()
        mock_upsert.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@patch("app.api.routes.documents.upsert_chunks")
@patch("app.api.routes.documents.embed_texts", return_value=[[0.1] * 384])
def test_index_document_partial(mock_embed, mock_upsert):
    """One chunk already indexed, one new → only the new chunk is embedded and upserted."""
    doc = _make_doc()
    chunk_already = _make_chunk(doc.id, 0, "already indexed")
    chunk_already.chroma_id = str(chunk_already.id)
    chunk_already.chroma_collection = "enterprise_knowledge_chunks"

    chunk_new = _make_chunk(doc.id, 1, "needs indexing")

    chunks = [chunk_already, chunk_new]

    app.dependency_overrides[get_db_session] = _index_db_override(doc, chunks)
    try:
        response = client.post(f"/documents/{doc.id}/index")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "vector_indexed"
        assert data["chunk_count"] == 2
        assert data["indexed_chunk_count"] == 1
        assert data["skipped_chunk_count"] == 1
        mock_embed.assert_called_once_with(["needs indexing"])
        call_kwargs = mock_upsert.call_args.kwargs
        assert call_kwargs["ids"] == [str(chunk_new.id)]
    finally:
        app.dependency_overrides.clear()
