import uuid
from datetime import UTC
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Document, DocumentChunk
from app.db.session import get_db_session
from app.schemas.chunks import ChunkingSummaryResponse, ChunkListResponse, ChunkResponse
from app.schemas.documents import DocumentListItem, DocumentResponse
from app.schemas.indexing import IndexingSummaryResponse
from app.services.chunking import chunk_text
from app.services.document_storage import save_upload_file
from app.services.embeddings import embed_texts
from app.services.text_extraction import SUPPORTED_EXTENSIONS, extract_text
from app.services.vector_store import delete_chunks_by_document, upsert_chunks

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
    chunk_size: int = Query(default=500, gt=0),
    chunk_overlap: int = Query(default=50, ge=0),
) -> ChunkingSummaryResponse:
    if chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=422,
            detail=(
                f"chunk_overlap ({chunk_overlap}) must be less than "
                f"chunk_size ({chunk_size})."
            ),
        )

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

    metadata = document.document_metadata or {}
    needs_vector_cleanup = (
        document.status == "vector_indexed" or bool(metadata.get("chroma_collection"))
    )
    document.status = "processing"
    await db.commit()

    try:
        settings = get_settings()
        if needs_vector_cleanup:
            delete_chunks_by_document(settings.chroma_collection_name, str(document_id))
        await db.execute(
            sa_delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        )

        text_chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for index, (chunk_content, token_count) in enumerate(text_chunks):
            db.add(
                DocumentChunk(
                    document_id=document_id,
                    chunk_index=index,
                    content=chunk_content,
                    token_count=token_count,
                )
            )

        document.status = "chunked"
        document.chunk_count = len(text_chunks)
        document.document_metadata = {
            key: value
            for key, value in (document.document_metadata or {}).items()
            if key not in {"indexed_at", "embedding_model", "chroma_collection"}
        }
        await db.commit()

    except Exception as exc:
        document.status = "failed"
        await db.commit()
        raise HTTPException(status_code=500, detail="Chunking failed unexpectedly.") from exc

    return ChunkingSummaryResponse(
        document_id=document_id,
        status="chunked",
        chunk_count=len(text_chunks),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )


@router.post("/{document_id}/index", response_model=IndexingSummaryResponse)
async def index_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> IndexingSummaryResponse:
    from datetime import datetime

    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")

    chunks_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    chunks = chunks_result.scalars().all()

    if not chunks:
        raise HTTPException(
            status_code=400,
            detail="Document has no chunks. Run POST /chunk first.",
        )

    settings = get_settings()
    document.status = "processing"
    await db.commit()

    new_chunks = [
        c for c in chunks
        if c.chroma_id is None or c.chroma_collection != settings.chroma_collection_name
    ]
    skipped_count = len(chunks) - len(new_chunks)

    if new_chunks:
        texts = [chunk.content for chunk in new_chunks]

        try:
            embeddings = embed_texts(texts)
        except Exception as exc:
            document.status = "failed"
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Embedding failed: {exc}") from exc

        ids = [str(chunk.id) for chunk in new_chunks]
        metadatas = [
            {
                "document_id": str(document_id),
                "chunk_id": str(chunk.id),
                "chunk_index": chunk.chunk_index,
                "filename": document.filename,
                "token_count": chunk.token_count or 0,
            }
            for chunk in new_chunks
        ]

        try:
            upsert_chunks(
                collection_name=settings.chroma_collection_name,
                ids=ids,
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
            )
        except RuntimeError as exc:
            document.status = "failed"
            await db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        for chunk in new_chunks:
            chunk.chroma_collection = settings.chroma_collection_name
            chunk.chroma_id = str(chunk.id)

    document.status = "vector_indexed"
    document.document_metadata = {
        **(document.document_metadata or {}),
        "indexed_at": datetime.now(UTC).isoformat(),
        "embedding_model": settings.embedding_model_name,
        "chroma_collection": settings.chroma_collection_name,
    }
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        current = await db.get(Document, document_id)
        if current is not None:
            current.status = "failed"
            await db.commit()
        raise HTTPException(
            status_code=500, detail="Failed to persist indexing state."
        ) from exc

    return IndexingSummaryResponse(
        document_id=document_id,
        status="vector_indexed",
        chunk_count=len(chunks),
        indexed_chunk_count=len(new_chunks),
        skipped_chunk_count=skipped_count,
        embedding_model=settings.embedding_model_name,
        chroma_collection=settings.chroma_collection_name,
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


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    if document.status in {"queued", "processing", "deleting"}:
        raise HTTPException(
            status_code=409, detail="Document processing or deletion is already active."
        )

    document.status = "deleting"
    await db.commit()

    try:
        settings = get_settings()
        delete_chunks_by_document(settings.chroma_collection_name, str(document_id))

        saved_path = (document.document_metadata or {}).get("saved_path")
        if saved_path:
            file_path = Path(saved_path)
            if file_path.exists():
                file_path.unlink()

        await db.delete(document)
        await db.commit()
    except Exception as exc:
        await db.rollback()
        current = await db.get(Document, document_id)
        if current is not None:
            current.status = "delete_failed"
            await db.commit()
        if isinstance(exc, RuntimeError):
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail="Document deletion failed.") from exc
