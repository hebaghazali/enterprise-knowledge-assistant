import uuid

from pydantic import BaseModel


class IndexingSummaryResponse(BaseModel):
    document_id: uuid.UUID
    status: str
    chunk_count: int
    indexed_chunk_count: int
    skipped_chunk_count: int
    embedding_model: str
    chroma_collection: str
