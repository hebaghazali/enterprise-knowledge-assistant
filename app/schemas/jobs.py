from datetime import datetime

from pydantic import BaseModel


class JobAcceptedResponse(BaseModel):
    job_id: str
    document_id: str
    status: str


class IngestionJobResponse(JobAcceptedResponse):
    predecessor_job_id: str | None
    job_type: str
    current_stage: str | None
    progress_current: int
    progress_total: int
    attempt_count: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
