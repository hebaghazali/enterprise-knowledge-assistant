import uuid

from pydantic import BaseModel


class ChunkResponse(BaseModel):
    id: uuid.UUID
    chunk_index: int
    content_preview: str
    token_count: int | None


class ChunkListResponse(BaseModel):
    document_id: uuid.UUID
    chunk_count: int
    chunks: list[ChunkResponse]


class ChunkingSummaryResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    chunk_count: int
    chunk_size: int
    chunk_overlap: int
