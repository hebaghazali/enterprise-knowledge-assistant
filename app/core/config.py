from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Enterprise Knowledge Assistant API"
    environment: str = "local"
    debug: bool = True
    api_version: str = "0.1.0"

    database_url: str = "postgresql+psycopg://eka_user:eka_password@localhost:5432/eka_db"
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection_name: str = "enterprise_knowledge_chunks"
    upload_dir: str = "storage/uploads"
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_query_tokens: int = 512

    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout_seconds: int = 120

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
