from pydantic import BaseModel, Field


class AnswerRequest(BaseModel):
    question: str
    k: int = Field(default=5, ge=1, le=10)


class AnswerSourceResponse(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    similarity_score: float
    content_preview: str


class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[AnswerSourceResponse]
    model: str
    k: int
