from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

# SQLAlchemy async requires the psycopg_async dialect; the canonical URL uses the
# sync dialect so Alembic can also use it without any transformation.
_async_url = settings.database_url.replace(
    "postgresql+psycopg://",
    "postgresql+psycopg_async://",
    1,
)

engine = create_async_engine(_async_url, echo=settings.debug)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
