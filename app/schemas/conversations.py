from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.answering import AnswerSourceResponse


class ConversationResponse(BaseModel):
    conversation_id: str
    created_at: datetime


class MessageResponse(BaseModel):
    message_id: str
    role: str
    content: str
    created_at: datetime


class ConversationDetailResponse(BaseModel):
    conversation_id: str
    created_at: datetime
    messages: list[MessageResponse]


class SendMessageRequest(BaseModel):
    message: str
    k: int = Field(default=5, ge=1, le=10)


class SendMessageResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    sources: list[AnswerSourceResponse]
