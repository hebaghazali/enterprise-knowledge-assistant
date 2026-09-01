import asyncio
import signal
import socket
import uuid
from contextlib import suppress
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select, update

from app.api.routes.documents import chunk_document, index_document
from app.core.config import get_settings
from app.db.models import Document, IngestionJob
from app.db.session import AsyncSessionLocal


def _utcnow() -> datetime:
    return datetime.now(UTC)


class IngestionWorker:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.worker_id = f"{socket.gethostname()}-{uuid.uuid4()}"
        self.stop_event = asyncio.Event()

    async def recover_stale_jobs(self) -> None:
        stale_before = _utcnow() - timedelta(
            seconds=self.settings.worker_stale_after_seconds
        )
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.status == "running",
                    IngestionJob.heartbeat_at < stale_before,
                )
                .values(
                    status="queued",
                    current_stage=None,
                    worker_id=None,
                    heartbeat_at=None,
                    error_message="Recovered after an interrupted worker.",
                )
            )
            await db.commit()

    async def claim_job(self) -> uuid.UUID | None:
        async with AsyncSessionLocal() as db:
            async with db.begin():
                result = await db.execute(
                    select(IngestionJob)
                    .where(IngestionJob.status == "queued")
                    .order_by(IngestionJob.created_at.asc())
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                job = result.scalar_one_or_none()
                if job is None:
                    return None
                now = _utcnow()
                job.status = "running"
                job.current_stage = "extracting"
                job.started_at = now
                job.heartbeat_at = now
                job.worker_id = self.worker_id
                job.attempt_count += 1
                job.error_message = None
                return job.id

    async def update_job(self, job_id: uuid.UUID, **values: object) -> None:
        async with AsyncSessionLocal() as db:
            values["heartbeat_at"] = _utcnow()
            await db.execute(
                update(IngestionJob)
                .where(
                    IngestionJob.id == job_id,
                    IngestionJob.worker_id == self.worker_id,
                )
                .values(**values)
            )
            await db.commit()

    async def heartbeat(self, job_id: uuid.UUID) -> None:
        while True:
            await asyncio.sleep(15)
            await self.update_job(job_id)

    async def process_job(self, job_id: uuid.UUID) -> None:
        heartbeat_task = asyncio.create_task(self.heartbeat(job_id))
        try:
            async with AsyncSessionLocal() as db:
                job = await db.get(IngestionJob, job_id)
                if job is None:
                    return
                document_id = job.document_id

                await self.update_job(job_id, current_stage="chunking")
                chunk_result = await chunk_document(
                    document_id, db, chunk_size=500, chunk_overlap=50
                )
                await self.update_job(
                    job_id,
                    current_stage="embedding",
                    progress_current=0,
                    progress_total=chunk_result.chunk_count,
                )
                await index_document(document_id, db)
                await self.update_job(job_id, current_stage="indexing")
                await self.update_job(
                    job_id,
                    status="completed",
                    current_stage="completed",
                    progress_current=chunk_result.chunk_count,
                    progress_total=chunk_result.chunk_count,
                    completed_at=_utcnow(),
                    worker_id=None,
                )
        except Exception as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            message = detail if isinstance(detail, str) else str(detail)
            async with AsyncSessionLocal() as db:
                job = await db.get(IngestionJob, job_id)
                if job is not None:
                    document = await db.get(Document, job.document_id)
                    if document is not None:
                        document.status = "failed"
                    job.status = "failed"
                    job.error_message = message[:2000]
                    job.completed_at = _utcnow()
                    job.heartbeat_at = _utcnow()
                    job.worker_id = None
                    await db.commit()
        finally:
            heartbeat_task.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat_task

    async def run(self) -> None:
        await self.recover_stale_jobs()
        while not self.stop_event.is_set():
            job_id = await self.claim_job()
            if job_id is not None:
                await self.process_job(job_id)
                continue
            try:
                await asyncio.wait_for(
                    self.stop_event.wait(),
                    timeout=self.settings.worker_poll_interval_seconds,
                )
            except TimeoutError:
                pass


async def _main() -> None:
    worker = IngestionWorker()
    loop = asyncio.get_running_loop()
    for signame in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError):
            loop.add_signal_handler(signame, worker.stop_event.set)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(_main())
