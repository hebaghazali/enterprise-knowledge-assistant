import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document
from app.db.session import get_db_session
from app.schemas.documents import DocumentListItem, DocumentResponse
from app.services.document_storage import save_upload_file
from app.services.text_extraction import SUPPORTED_EXTENSIONS, extract_text

router = APIRouter(tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    file: UploadFile,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type '{ext}'. "
                f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            ),
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        text = extract_text(content, ext)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        saved_path, file_size = save_upload_file(content, file.filename or "upload")
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from exc

    original_filename = file.filename or "upload"
    document = Document(
        filename=original_filename,
        content_type=file.content_type,
        source_type="upload",
        status="uploaded",
        chunk_count=0,
        document_metadata={
            "original_filename": original_filename,
            "saved_path": str(saved_path),
            "file_size_bytes": file_size,
            "text_length": len(text),
            "extension": ext,
        },
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    return DocumentResponse.model_validate(document)


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> DocumentResponse:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    return DocumentResponse.model_validate(document)


@router.get("", response_model=list[DocumentListItem])
async def list_documents(
    db: AsyncSession = Depends(get_db_session),
) -> list[DocumentListItem]:
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc())
    )
    documents = result.scalars().all()
    return [DocumentListItem.model_validate(doc) for doc in documents]
