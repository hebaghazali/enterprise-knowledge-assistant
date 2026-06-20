from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.answer import router as answer_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.api.routes.search import router as search_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Enterprise Knowledge Assistant API",
    description="Local-first RAG backend for document-grounded conversational AI.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(documents_router, prefix="/documents")
app.include_router(search_router)
app.include_router(answer_router)
app.include_router(conversations_router)


@app.get("/")
async def root() -> dict:
    return {
        "name": settings.app_name,
        "version": settings.api_version,
        "status": "running",
    }
