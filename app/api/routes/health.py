from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.services.llm import OllamaUnavailableError, get_ollama_info
from app.services.vector_store import chroma_health

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "enterprise-knowledge-assistant"}


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db_session)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "database": "unavailable", "detail": str(exc)},
        ) from exc


async def _database_status(db: AsyncSession) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "error", "detail": "Database connection failed."}


async def _chroma_status() -> dict:
    try:
        return await run_in_threadpool(chroma_health)
    except RuntimeError as exc:
        return {"status": "error", "detail": str(exc)}


async def _ollama_status() -> dict:
    settings = get_settings()
    try:
        info = await get_ollama_info(
            settings.ollama_base_url,
            settings.ollama_model,
            min(settings.ollama_timeout_seconds, 10),
        )
    except OllamaUnavailableError as exc:
        return {
            "status": "error",
            "configured_model": settings.ollama_model,
            "detail": str(exc),
        }
    if not info["configured_model_present"]:
        info["detail"] = "Configured model is not installed."
    return info


@router.get("/health/chroma")
async def health_chroma() -> dict:
    result = await _chroma_status()
    if result["status"] != "ok":
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/health/ollama")
async def health_ollama() -> dict:
    result = await _ollama_status()
    if result["status"] != "ok":
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/health/ready")
async def health_ready(db: AsyncSession = Depends(get_db_session)) -> dict:
    database = await _database_status(db)
    chroma = await _chroma_status()
    ollama = await _ollama_status()
    services = {
        "api": {"status": "ok"},
        "postgresql": database,
        "chroma": chroma,
        "ollama": ollama,
    }
    ready = all(service["status"] == "ok" for service in services.values())
    result = {"status": "ok" if ready else "degraded", "services": services}
    if not ready:
        raise HTTPException(status_code=503, detail=result)
    return result
