import uuid

from pydantic import BaseModel


class SearchResultResponse(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    content: str
    token_count: int | None
    similarity_score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultResponse]
    result_count: int
