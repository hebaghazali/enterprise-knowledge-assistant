import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.db.session import get_db_session
from app.schemas.chunks import ChunkListResponse, ChunkResponse, ChunkingSummaryResponse
from app.schemas.documents import DocumentListItem, DocumentResponse
from app.services.chunking import chunk_text, estimate_token_count
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

    original_filename = file.filename or "upload"
    document_id = uuid.uuid4()

    try:
        upload_dir = Path(get_settings().upload_dir)
        saved_path, file_size = save_upload_file(
            content, original_filename, upload_dir, document_id=document_id
        )
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.") from exc

    document = Document(
        id=document_id,
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


@router.post("/{document_id}/chunk", response_model=ChunkingSummaryResponse)
async def chunk_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> ChunkingSummaryResponse:
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    saved_path = (document.document_metadata or {}).get("saved_path")
    if not saved_path:
        raise HTTPException(status_code=400, detail="No saved file path in document metadata.")

    file_path = Path(saved_path)
    if not file_path.exists():
        raise HTTPException(status_code=400, detail="Uploaded file not found on disk.")

    ext = (document.document_metadata or {}).get(
        "extension", Path(document.filename).suffix.lower()
    )
    try:
        file_content = file_path.read_bytes()
        text = extract_text(file_content, ext)
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not text.strip():
        raise HTTPException(status_code=400, detail="No extractable text found in document.")

    document.status = "processing"
    await db.commit()

    try:
        await db.execute(
            sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

        text_chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for index, chunk_content in enumerate(text_chunks):
            db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=chunk_content,
                    token_count=estimate_token_count(chunk_content),
                )
            )

        document.status = "indexed"
        document.chunk_count = len(text_chunks)
        await db.commit()

    except Exception as exc:
        document.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail="Chunking failed unexpectedly.") from exc

    return ChunkingSummaryResponse(
        document_id=document_id,
        status="indexed",
        chunk_count=len(text_chunks),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@router.get("/{document_id}/chunks", response_model=ChunkListResponse)
async def get_document_chunks(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> ChunkListResponse:
    result = await db.execute(select(Document).where(Document.id == document_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    chunk_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = chunk_result.scalars().all()

    return ChunkListResponse(
        document_id=document_id,
        chunk_count=len(chunks),
        chunks=[
            ChunkResponse(
                id=chunk.id,
                chunk_index=chunk.chunk_index,
                content_preview=chunk.content[:100],
                token_count=chunk.token_count,
            )
            for chunk in chunks
        ],
    )


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
    result = await db.execute(select(Document).order_by(Document.created_at.desc()))
    documents = result.scalars().all()
    return [DocumentListItem.model_validate(doc) for doc in documents]
