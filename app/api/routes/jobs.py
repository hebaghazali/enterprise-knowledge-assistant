import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, IngestionJob
from app.db.session import get_db_session
from app.schemas.jobs import IngestionJobResponse, JobAcceptedResponse

router = APIRouter(tags=["ingestion jobs"])
_ACTIVE_STATUSES = ("queued", "running")


async def _commit_queued_job(db: AsyncSession) -> None:
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Document already has an active job."
        ) from exc


def _response(job: IngestionJob) -> IngestionJobResponse:
    return IngestionJobResponse(
        job_id=str(job.id),
        document_id=str(job.document_id),
        predecessor_job_id=str(job.predecessor_job_id) if job.predecessor_job_id else None,
        job_type=job.job_type,
        status=job.status,
        current_stage=job.current_stage,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
        attempt_count=job.attempt_count,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )


async def _ensure_no_active_job(db: AsyncSession, document_id: uuid.UUID) -> None:
    result = await db.execute(
        select(IngestionJob.id).where(
            IngestionJob.document_id == document_id,
            IngestionJob.status.in_(_ACTIVE_STATUSES),
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Document already has an active job.")


@router.post(
    "/documents/{document_id}/process",
    response_model=JobAcceptedResponse,
    status_code=202,
)
async def process_document(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobAcceptedResponse:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    await _ensure_no_active_job(db, document_id)
    job = IngestionJob(id=uuid.uuid4(), document_id=document_id, status="queued")
    db.add(job)
    document.status = "queued"
    await _commit_queued_job(db)
    return JobAcceptedResponse(
        job_id=str(job.id), document_id=str(document_id), status=job.status
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
async def get_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestionJobResponse:
    job = await db.get(IngestionJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _response(job)


@router.get(
    "/documents/{document_id}/jobs", response_model=list[IngestionJobResponse]
)
async def list_document_jobs(
    document_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = Query(default=10, ge=1, le=100),
) -> list[IngestionJobResponse]:
    if await db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    result = await db.execute(
        select(IngestionJob)
        .where(IngestionJob.document_id == document_id)
        .order_by(IngestionJob.created_at.desc())
        .limit(limit)
    )
    return [_response(job) for job in result.scalars().all()]


@router.post("/jobs/{job_id}/retry", response_model=JobAcceptedResponse, status_code=202)
async def retry_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> JobAcceptedResponse:
    previous = await db.get(IngestionJob, job_id)
    if previous is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if previous.status not in {"failed", "cancelled"}:
        raise HTTPException(status_code=409, detail="Only failed or cancelled jobs can be retried.")
    await _ensure_no_active_job(db, previous.document_id)
    job = IngestionJob(
        id=uuid.uuid4(),
        document_id=previous.document_id,
        predecessor_job_id=previous.id,
        status="queued",
        attempt_count=previous.attempt_count,
    )
    db.add(job)
    document = await db.get(Document, previous.document_id)
    if document is not None:
        document.status = "queued"
    await _commit_queued_job(db)
    return JobAcceptedResponse(
        job_id=str(job.id), document_id=str(job.document_id), status=job.status
    )
