from fastapi import FastAPI

from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Enterprise Knowledge Assistant API",
    description="Local-first RAG backend for document-grounded conversational AI.",
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(documents_router, prefix="/documents")


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "status": "running",
    }
