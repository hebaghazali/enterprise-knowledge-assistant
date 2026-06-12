# Enterprise Knowledge Assistant

A local-first, zero-cost Generative AI backend that lets you upload documents and ask questions against them using a fully local stack — no cloud APIs, no per-token costs.

## What this project does (eventually)

- Accept document uploads (PDF, text, etc.)
- Chunk and embed documents using local sentence-transformers
- Store vectors in ChromaDB
- Answer user questions with context retrieved from uploaded documents
- Use a locally running LLM via Ollama for generation
- Expose a conversational REST API via FastAPI

## Current scope (PR 3)

PostgreSQL persistence foundation:

- **SQLAlchemy 2.0 async** engine and session
- **Alembic** migrations with initial schema
- **5 database models**: Document, DocumentChunk, Conversation, Message, LLMRun
- **`GET /health/db`** endpoint to verify database connectivity

No document upload, embeddings, or RAG yet.

PR 2: Docker Compose for API, PostgreSQL, ChromaDB.
PR 1: FastAPI skeleton, health endpoint, config, tests.

## Planned tech stack

| Layer | Tool |
|---|---|
| API | FastAPI |
| Relational DB | PostgreSQL |
| Vector DB | ChromaDB |
| LLM | Ollama (local) |
| Embeddings | sentence-transformers |
| ORM | SQLAlchemy + Alembic |
| Orchestration | LangChain |
| Containerisation | Docker Compose |
| Testing | pytest + httpx |

## Local setup (Docker — recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env
docker compose up --build
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| ChromaDB | http://localhost:8001 |

Run database migrations (in a second terminal after `docker compose up`):

```bash
docker compose exec api alembic upgrade head
```

Test the running API:

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/health/db
```

Stop services:

```bash
docker compose down        # stop containers
docker compose down -v     # stop and delete volumes
```

## Local setup (without Docker)

**With pip:**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env
```

**With uv (faster):**

```bash
uv venv
uv pip install -e ".[dev]"
cp .env.example .env
```

Run the API:

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

## Running tests

```bash
pytest
```

## Database migrations

```bash
# Apply all migrations
alembic upgrade head

# Generate a new migration after changing models
alembic revision --autogenerate -m "describe the change"

# Roll back one migration
alembic downgrade -1
```

Inside Docker:

```bash
docker compose exec api alembic upgrade head
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Project info |
| GET | `/health` | App process health (no DB dependency) |
| GET | `/health/db` | Database connectivity check |

## Roadmap

| PR | Scope |
|---|---|
| PR 1 | Project skeleton, health endpoint, config |
| PR 2 | Docker Compose for API, PostgreSQL, ChromaDB |
| PR 3 (this) | Database models, SQLAlchemy, Alembic migrations |
| PR 4 | Document upload endpoint, chunking pipeline |
| PR 5 | Embeddings with sentence-transformers + ChromaDB storage |
| PR 6 | Ollama integration, RAG query endpoint |
| PR 7 | Conversation history, session management |
| PR 8 | Frontend UI (optional) |
