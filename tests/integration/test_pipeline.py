import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.main import app
from app.worker import IngestionWorker

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="Set RUN_INTEGRATION=1 with PostgreSQL and ChromaDB available.",
    ),
]


def _chunks(text: str, **_: int) -> list[tuple[str, int]]:
    return [(text, len(text.split()))]


def _embeddings(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0, 0.0] for _ in texts]


async def _run_next_job() -> None:
    worker = IngestionWorker()
    job_id = await worker.claim_job()
    assert job_id is not None
    await worker.process_job(job_id)


@pytest.mark.asyncio
async def test_upload_process_search_answer_reprocess_delete_pipeline():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        upload = await client.post(
            "/documents/upload",
            files={
                "file": (
                    "policy.txt",
                    b"Employees may work remotely three days per week.",
                    "text/plain",
                )
            },
        )
        assert upload.status_code == 201, upload.text
        document_id = upload.json()["id"]

        first_job = await client.post(f"/documents/{document_id}/process")
        assert first_job.status_code == 202, first_job.text

        with (
            patch("app.api.routes.documents.chunk_text", side_effect=_chunks),
            patch("app.api.routes.documents.embed_texts", side_effect=_embeddings),
        ):
            await _run_next_job()

        job = await client.get(f"/jobs/{first_job.json()['job_id']}")
        assert job.json()["status"] == "completed"
        first_chunks = await client.get(f"/documents/{document_id}/chunks")
        first_chunk_id = first_chunks.json()["chunks"][0]["id"]

        with (
            patch("app.api.routes.search.count_query_tokens", return_value=5),
            patch("app.services.retrieval.embed_text", return_value=[1.0, 0.0, 0.0]),
        ):
            search = await client.get("/search", params={"q": "remote work", "k": 3})
        assert search.status_code == 200, search.text
        assert search.json()["results"][0]["document_id"] == document_id

        with (
            patch("app.api.routes.answer.count_query_tokens", return_value=5),
            patch("app.services.retrieval.embed_text", return_value=[1.0, 0.0, 0.0]),
            patch(
                "app.services.answering.call_ollama",
                new=AsyncMock(return_value="Three days per week. [Source 1]"),
            ),
        ):
            answer = await client.post(
                "/answer", json={"question": "How often is remote work allowed?", "k": 3}
            )
        assert answer.status_code == 200, answer.text
        assert answer.json()["answer"]
        assert answer.json()["sources"][0]["document_id"] == document_id

        if os.getenv("RUN_REAL_OLLAMA") == "1":
            with (
                patch("app.api.routes.answer.count_query_tokens", return_value=5),
                patch(
                    "app.services.retrieval.embed_text", return_value=[1.0, 0.0, 0.0]
                ),
            ):
                real_answer = await client.post(
                    "/answer",
                    json={"question": "How often is remote work allowed?", "k": 3},
                )
            assert real_answer.status_code == 200, real_answer.text
            assert real_answer.json()["answer"].strip()
            assert real_answer.json()["sources"]

        second_job = await client.post(f"/documents/{document_id}/process")
        assert second_job.status_code == 202, second_job.text
        with (
            patch("app.api.routes.documents.chunk_text", side_effect=_chunks),
            patch("app.api.routes.documents.embed_texts", side_effect=_embeddings),
        ):
            await _run_next_job()

        second_chunks = await client.get(f"/documents/{document_id}/chunks")
        second_chunk_id = second_chunks.json()["chunks"][0]["id"]
        assert second_chunk_id != first_chunk_id

        with (
            patch("app.api.routes.search.count_query_tokens", return_value=5),
            patch("app.services.retrieval.embed_text", return_value=[1.0, 0.0, 0.0]),
        ):
            refreshed = await client.get(
                "/search", params={"q": "remote work", "k": 3}
            )
        refreshed_ids = {item["chunk_id"] for item in refreshed.json()["results"]}
        assert first_chunk_id not in refreshed_ids
        assert second_chunk_id in refreshed_ids

        deleted = await client.delete(f"/documents/{document_id}")
        assert deleted.status_code == 204, deleted.text
        assert (await client.get(f"/documents/{document_id}")).status_code == 404
        with (
            patch("app.api.routes.search.count_query_tokens", return_value=5),
            patch("app.services.retrieval.embed_text", return_value=[1.0, 0.0, 0.0]),
        ):
            empty_search = await client.get(
                "/search", params={"q": "remote work", "k": 3}
            )
        assert empty_search.status_code == 404
