FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .

RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    pydantic \
    pydantic-settings \
    python-dotenv \
    "sqlalchemy[asyncio]" \
    alembic \
    "psycopg[binary]" \
    python-multipart \
    pypdf \
    transformers \
    sentence-transformers \
    chromadb

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
