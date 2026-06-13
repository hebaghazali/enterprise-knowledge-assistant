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
    upload_dir: str = "storage/uploads"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
