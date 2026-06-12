import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import Document
from app.db.session import get_db_session
from app.main import app
from app.services.text_extraction import extract_text

client = TestClient(app)

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
    # Set fields that SQLAlchemy normally populates at flush/refresh time.
    doc.id = uuid.uuid4()
    doc.created_at = _NOW
    doc.updated_at = _NOW
    return doc


def _upload_db_override(doc: Document):
    """DB dependency override that captures the Document added and refreshes it."""

    async def _override():
        session = MagicMock()
        session.add = MagicMock()
        session.commit = AsyncMock()

        async def _refresh(obj):
            # Simulate DB setting generated fields if not already set.
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
