from fastapi import APIRouter, HTTPException

from app.core.config import get_settings
from app.services.llm import OllamaUnavailableError, get_ollama_info

router = APIRouter(prefix="/models", tags=["models"])


@router.get("")
async def list_models() -> dict:
    settings = get_settings()
    try:
        return await get_ollama_info(
            settings.ollama_base_url,
            settings.ollama_model,
            min(settings.ollama_timeout_seconds, 10),
        )
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/configured")
async def configured_model() -> dict:
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
            "configured_model_present": False,
            "detail": str(exc),
        }
    return {
        "status": info["status"],
        "configured_model": info["configured_model"],
        "configured_model_present": info["configured_model_present"],
        "version": info["version"],
    }
