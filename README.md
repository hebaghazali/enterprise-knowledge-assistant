# Enterprise Knowledge Assistant

A local-first, zero-cost Generative AI backend that lets you upload documents and ask questions against them using a fully local stack — no cloud APIs, no per-token costs.

## What this project does (eventually)

- Accept document uploads (PDF, text, etc.)
- Chunk and embed documents using local sentence-transformers
- Store vectors in ChromaDB
- Answer user questions with context retrieved from uploaded documents
- Use a locally running LLM via Ollama for generation
- Expose a conversational REST API via FastAPI

## Current scope (PR 1)

This PR establishes the clean project foundation only:

- FastAPI app skeleton
- Health endpoint (`GET /health`)
- Root info endpoint (`GET /`)
- Settings/config via pydantic-settings
- Basic test suite
- pyproject.toml with dependency management

No Docker, no database, no LLM, no document upload yet.

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

## Local setup

**With pip:**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

**With uv (faster):**

```bash
uv venv
uv pip install -e ".[dev]"
```

Copy the example env file:

```bash
cp .env.example .env
```

## Running the API

```bash
uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

## Running tests

```bash
pytest
```

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Project info |
| GET | `/health` | Health check |

## Roadmap

| PR | Scope |
|---|---|
| PR 1 (this) | Project skeleton, health endpoint, config |
| PR 2 | Docker Compose for API, PostgreSQL, ChromaDB |
| PR 3 | Database models, SQLAlchemy, Alembic migrations |
| PR 4 | Document upload endpoint, chunking pipeline |
| PR 5 | Embeddings with sentence-transformers + ChromaDB storage |
| PR 6 | Ollama integration, RAG query endpoint |
| PR 7 | Conversation history, session management |
| PR 8 | Frontend UI (optional) |
