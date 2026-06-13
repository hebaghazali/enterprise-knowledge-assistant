import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import Document, DocumentChunk
from app.db.session import get_db_session
from app.main import app
from app.services.chunking import chunk_text, estimate_token_count
from app.services.document_storage import save_upload_file
from app.services.text_extraction import extract_text

client = TestClient(app)

# ---------------------------------------------------------------------------
# save_upload_file — unit tests using a temp directory
# ---------------------------------------------------------------------------


def test_save_upload_file_creates_directory(tmp_path):
    upload_dir = tmp_path / "storage" / "uploads"
    assert not upload_dir.exists()
    save_upload_file(b"hello", "test.txt", upload_dir)
    assert upload_dir.is_dir()


def test_save_upload_file_writes_content(tmp_path):
    upload_dir = tmp_path / "uploads"
    content = b"Company policy document."
    path, size = save_upload_file(content, "policy.txt", upload_dir)
    assert path.exists()
    assert path.read_bytes() == content
    assert size == len(content)


def test_save_upload_file_relative_path_structure(tmp_path):
    upload_dir = tmp_path / "uploads"
    path, _ = save_upload_file(b"data", "doc.txt", upload_dir)
    assert path.parent == upload_dir
    assert path.name.endswith("_doc.txt")


def test_save_upload_file_uses_document_id_as_prefix(tmp_path):
    upload_dir = tmp_path / "uploads"
    document_id = uuid.uuid4()
    path, _ = save_upload_file(b"content", "report.txt", upload_dir, document_id=document_id)
    assert path.name.startswith(str(document_id))
    assert path.name == f"{document_id}_report.txt"


def test_save_upload_file_sanitises_filename(tmp_path):
    upload_dir = tmp_path / "uploads"
    path, _ = save_upload_file(b"x", "my file (1).txt", upload_dir)
    assert " " not in path.name
    assert "(" not in path.name
    assert ")" not in path.name


# ---------------------------------------------------------------------------
# Text extraction — pure unit tests, no mocking needed
# ---------------------------------------------------------------------------


def test_extract_txt():
    assert extract_text(b"Hello world", ".txt") == "Hello world"


def test_extract_md():
    content = b"# Title\n\nSome content"
    assert extract_text(content, ".md") == "# Title\n\nSome content"


def test_extract_unsupported_raises():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text(b"data", ".docx")


# ---------------------------------------------------------------------------
# chunk_text — unit tests
# ---------------------------------------------------------------------------


def test_chunk_empty_text():
    assert chunk_text("") == []


def test_chunk_whitespace_only():
    assert chunk_text("   \n  ") == []


def test_chunk_shorter_than_chunk_size():
    text = "Hello world"
    assert chunk_text(text, chunk_size=500, chunk_overlap=50) == ["Hello world"]


def test_chunk_exact_chunk_size():
    text = "A" * 500
    result = chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert result == ["A" * 500]


def test_chunk_overlap_behavior():
    # ABCDEFGHIJ with size=5, overlap=2 → step=3
    # chunks: [0:5]=ABCDE, [3:8]=DEFGH, [6:10]=GHIJ
    text = "ABCDEFGHIJ"
    result = chunk_text(text, chunk_size=5, chunk_overlap=2)
    assert result == ["ABCDE", "DEFGH", "GHIJ"]


def test_chunk_correct_count_large_text():
    # 1000 chars, size=500, overlap=50 → step=450
    # start=0→500, start=450→950, start=900→1000 → 3 chunks
    text = "A" * 1000
    result = chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert len(result) == 3
    assert len(result[0]) == 500
    assert len(result[1]) == 500
    assert len(result[2]) == 100


def test_chunk_overlap_gte_chunk_size_terminates():
    # overlap >= chunk_size must not loop forever; step is clamped to 1
    text = "Hello world"
    result = chunk_text(text, chunk_size=3, chunk_overlap=10)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# estimate_token_count — unit tests
# ---------------------------------------------------------------------------


def test_estimate_token_count_empty():
    assert estimate_token_count("") == 0


def test_estimate_token_count_positive():
    assert estimate_token_count("hello world") > 0


def test_estimate_token_count_not_word_split():
    # "tokenization" is 1 whitespace-word but splits into 2 WordPiece subwords,
    # proving the real tokenizer is used rather than text.split().
    text = "tokenization"
    assert estimate_token_count(text) > len(text.split())


# ---------------------------------------------------------------------------
# Helpers for endpoint tests
# ---------------------------------------------------------------------------

_FAKE_PATH = Path("storage/uploads/fake-uuid_test.txt")
_NOW = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)


def _make_document(filename: str = "test.txt", ext: str = ".txt") -> Document:
    """Build a Document ORM instance with all fields pre-populated."""
    doc = Document(
        filename=filename,
        content_type="text/plain",
        source_type="upload",
        status="uploaded",
        chunk_count=0,
        document_metadata={
            "original_filename": filename,
            "saved_path": str(_FAKE_PATH),
            "file_size_bytes": 41,
            "text_length": 41,
            "extension": ext,
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
        token_count=estimate_token_count(content),
    )
    chunk.id = uuid.uuid4()
    chunk.created_at = _NOW
    return chunk


def _upload_db_override(doc: Document):
    """DB dependency override that captures the Document added and refreshes it."""

    async def _override():
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        async def _refresh(obj):
            if not getattr(obj, "id", None):
                obj.id = doc.id
            if not getattr(obj, "created_at", None):
                obj.created_at = doc.created_at
            if not getattr(obj, "updated_at", None):
                obj.updated_at = doc.updated_at

        session.refresh = AsyncMock(side_effect=_refresh)
        yield session

    return _override


def _query_db_override(doc: Document | None):
    """DB dependency override whose execute() returns the given document (or None)."""

    async def _override():
        session = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = doc
        mock_result.scalars.return_value.all.return_value = [doc] if doc else []
        session.execute = AsyncMock(return_value=mock_result)
        yield session

    return _override


def _chunk_db_override(doc: Document):
    """DB dependency override for POST /{document_id}/chunk.

    Expects two execute calls: SELECT Document, then DELETE DocumentChunk.
    """

    async def _override():
        session = MagicMock()

        mock_select = MagicMock()
        mock_select.scalar_one_or_none.return_value = doc

        mock_delete = MagicMock()

        session.execute = AsyncMock(side_effect=[mock_select, mock_delete])
        session.add = MagicMock()
        session.commit = AsyncMock()
        yield session

    return _override


def _chunks_list_db_override(doc: Document, chunks: list[DocumentChunk]):
    """DB dependency override for GET /{document_id}/chunks."""

    async def _override():
        session = MagicMock()

        mock_doc_result = MagicMock()
        mock_doc_result.scalar_one_or_none.return_value = doc

        mock_chunks_result = MagicMock()
        mock_chunks_result.scalars.return_value.all.return_value = chunks

        session.execute = AsyncMock(side_effect=[mock_doc_result, mock_chunks_result])
        yield session

    return _override


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------


@patch(
    "app.api.routes.documents.save_upload_file",
    return_value=(_FAKE_PATH, 41),
)
def test_upload_txt_success(mock_save):
    doc = _make_document("test.txt", ".txt")
    app.dependency_overrides[get_db_session] = _upload_db_override(doc)
    try:
        response = client.post(
            "/documents/upload",
            files={"file": ("test.txt", b"This is a sample company policy document.", "text/plain")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["filename"] == "test.txt"
        assert data["status"] == "uploaded"
        assert data["source_type"] == "upload"
        assert data["chunk_count"] == 0
        assert "id" in data
        assert "created_at" in data
    finally:
        app.dependency_overrides.clear()


@patch(
    "app.api.routes.documents.save_upload_file",
    return_value=(_FAKE_PATH, 22),
)
def test_upload_md_success(mock_save):
    doc = _make_document("notes.md", ".md")
    app.dependency_overrides[get_db_session] = _upload_db_override(doc)
    try:
        response = client.post(
            "/documents/upload",
            files={"file": ("notes.md", b"# Heading\n\nSome notes.", "text/markdown")},
        )
        assert response.status_code == 201
        assert response.json()["filename"] == "notes.md"
    finally:
        app.dependency_overrides.clear()


def test_upload_saved_path_uses_document_id():
    """The document_id passed to save_upload_file must match the id in the API response."""
    doc = _make_document("test.txt", ".txt")
    captured: dict = {}

    def fake_save(content, filename, upload_dir, document_id=None):
        captured["document_id"] = document_id
        return (_FAKE_PATH, 41)

    with patch("app.api.routes.documents.save_upload_file", side_effect=fake_save):
        app.dependency_overrides[get_db_session] = _upload_db_override(doc)
        try:
            response = client.post(
                "/documents/upload",
                files={"file": ("test.txt", b"some content", "text/plain")},
            )
            assert response.status_code == 201
            data = response.json()
            assert captured["document_id"] is not None
            assert str(captured["document_id"]) == data["id"]
        finally:
            app.dependency_overrides.clear()


def test_upload_unsupported_extension():
    response = client.post(
        "/documents/upload",
        files={"file": ("report.docx", b"binary content", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_upload_empty_file():
    response = client.post(
        "/documents/upload",
        files={"file": ("empty.txt", b"", "text/plain")},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------


def test_get_document_found():
    doc = _make_document()
    app.dependency_overrides[get_db_session] = _query_db_override(doc)
    try:
        response = client.get(f"/documents/{doc.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(doc.id)
        assert data["filename"] == "test.txt"
        assert data["status"] == "uploaded"
        assert "metadata" in data
    finally:
        app.dependency_overrides.clear()


def test_get_document_not_found():
    app.dependency_overrides[get_db_session] = _query_db_override(None)
    try:
        response = client.get(f"/documents/{uuid.uuid4()}")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /documents/{document_id}/chunk
# ---------------------------------------------------------------------------


def test_chunk_document_success(tmp_path):
    content = b"A" * 600  # 2 chunks: [0:500], [450:600]
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(content)

    doc = _make_document("test.txt", ".txt")
    doc.document_metadata = {**doc.document_metadata, "saved_path": str(file_path)}

    app.dependency_overrides[get_db_session] = _chunk_db_override(doc)
    try:
        response = client.post(f"/documents/{doc.id}/chunk")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexed"
        assert data["chunk_count"] == 2
        assert data["chunk_size"] == 500
        assert data["chunk_overlap"] == 50
        assert data["document_id"] == str(doc.id)
    finally:
        app.dependency_overrides.clear()


def test_chunk_document_custom_params(tmp_path):
    content = b"B" * 200
    file_path = tmp_path / "doc.txt"
    file_path.write_bytes(content)

    doc = _make_document("doc.txt", ".txt")
    doc.document_metadata = {**doc.document_metadata, "saved_path": str(file_path)}

    app.dependency_overrides[get_db_session] = _chunk_db_override(doc)
    try:
        response = client.post(
            f"/documents/{doc.id}/chunk",
            params={"chunk_size": 100, "chunk_overlap": 10},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_size"] == 100
        assert data["chunk_overlap"] == 10
        # 200 chars, size=100, overlap=10, step=90 → chunks at 0, 90, 180 → 3 chunks
        assert data["chunk_count"] == 3
    finally:
        app.dependency_overrides.clear()


def test_chunk_document_rechunking_replaces_old_chunks(tmp_path):
    content = b"Hello world. " * 50  # ~650 bytes
    file_path = tmp_path / "rechunk.txt"
    file_path.write_bytes(content)

    doc = _make_document("rechunk.txt", ".txt")
    doc.document_metadata = {**doc.document_metadata, "saved_path": str(file_path)}
    doc.status = "indexed"
    doc.chunk_count = 99  # stale value — should be replaced

    app.dependency_overrides[get_db_session] = _chunk_db_override(doc)
    try:
        response = client.post(f"/documents/{doc.id}/chunk")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "indexed"
        assert data["chunk_count"] != 99
    finally:
        app.dependency_overrides.clear()


def test_chunk_document_not_found():
    app.dependency_overrides[get_db_session] = _query_db_override(None)
    try:
        response = client.post(f"/documents/{uuid.uuid4()}/chunk")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_chunk_document_missing_file():
    doc = _make_document("test.txt", ".txt")
    doc.document_metadata = {
        **doc.document_metadata,
        "saved_path": "/nonexistent/path/missing.txt",
    }

    app.dependency_overrides[get_db_session] = _query_db_override(doc)
    try:
        response = client.post(f"/documents/{doc.id}/chunk")
        assert response.status_code == 400
        assert "not found on disk" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /documents/{document_id}/chunks
# ---------------------------------------------------------------------------


def test_get_chunks_returns_ordered_previews():
    doc = _make_document()
    chunk_objects = [
        _make_chunk(doc.id, 0, "First chunk content here"),
        _make_chunk(doc.id, 1, "Second chunk content here"),
        _make_chunk(doc.id, 2, "Third chunk content here"),
    ]

    app.dependency_overrides[get_db_session] = _chunks_list_db_override(doc, chunk_objects)
    try:
        response = client.get(f"/documents/{doc.id}/chunks")
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_count"] == 3
        assert len(data["chunks"]) == 3
        assert data["chunks"][0]["chunk_index"] == 0
        assert data["chunks"][1]["chunk_index"] == 1
        assert data["chunks"][2]["chunk_index"] == 2
        assert "First chunk content here" in data["chunks"][0]["content_preview"]
    finally:
        app.dependency_overrides.clear()


def test_get_chunks_preview_truncated_to_100():
    doc = _make_document()
    long_content = "X" * 200
    chunk_objects = [_make_chunk(doc.id, 0, long_content)]

    app.dependency_overrides[get_db_session] = _chunks_list_db_override(doc, chunk_objects)
    try:
        response = client.get(f"/documents/{doc.id}/chunks")
        assert response.status_code == 200
        preview = response.json()["chunks"][0]["content_preview"]
        assert len(preview) == 100
    finally:
        app.dependency_overrides.clear()


def test_get_chunks_document_not_found():
    app.dependency_overrides[get_db_session] = _query_db_override(None)
    try:
        response = client.get(f"/documents/{uuid.uuid4()}/chunks")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_get_chunks_empty_when_not_yet_chunked():
    doc = _make_document()

    app.dependency_overrides[get_db_session] = _chunks_list_db_override(doc, [])
    try:
        response = client.get(f"/documents/{doc.id}/chunks")
        assert response.status_code == 200
        data = response.json()
        assert data["chunk_count"] == 0
        assert data["chunks"] == []
    finally:
        app.dependency_overrides.clear()
