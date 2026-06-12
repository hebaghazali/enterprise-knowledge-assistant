import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class DocumentResponse(BaseModel):
    id: uuid.UUID
    filename: str
    content_type: Optional[str] = None
    source_type: str
    status: str
    chunk_count: int
    # document_metadata is the ORM attribute; expose as "metadata" in the API.
    metadata: Optional[dict] = Field(None, validation_alias="document_metadata")
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @computed_field
    @property
    def text_length(self) -> Optional[int]:
        if self.metadata:
            return self.metadata.get("text_length")
        return None


class DocumentListItem(BaseModel):
    id: uuid.UUID
    filename: str
    source_type: str
    status: str
    chunk_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
