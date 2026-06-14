# Enterprise Knowledge Assistant

A local-first, zero-cost Generative AI backend that lets you upload documents and ask questions against them using a fully local stack — no cloud APIs, no per-token costs.

## What this project does (eventually)

- Accept document uploads (PDF, text, etc.)
- Chunk and embed documents using local sentence-transformers
- Store vectors in ChromaDB
- Answer user questions with context retrieved from uploaded documents
- Use a locally running LLM via Ollama for generation
- Expose a conversational REST API via FastAPI

## Current scope (PR 5)

Document chunking and PostgreSQL persistence:

- **`POST /documents/upload`** — accepts `.txt`, `.md`, `.pdf`; extracts text; saves file; stores document metadata in PostgreSQL
- **`POST /documents/{id}/chunk`** — splits extracted text into overlapping chunks and persists them in `document_chunks`; idempotent (re-chunking replaces existing chunks)
- **`GET /documents/{id}/chunks`** — list all chunks for a document with previews and token counts
- **`GET /documents/{id}`** — retrieve document metadata by UUID
- **`GET /documents`** — list all uploaded documents
- File storage under `storage/uploads/`

This PR prepares documents for future embedding generation and vector indexing. Embeddings and ChromaDB storage will be added in PR 6.

PR 4: Document upload, text extraction, file storage.
PR 3: Database models, SQLAlchemy, Alembic migrations.
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

## Document upload

Supported file types: `.txt`, `.md`, `.pdf`

Upload a file:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@path/to/document.txt"
```

Retrieve a document:

```bash
curl http://localhost:8000/documents/<document-id>
```

List all documents:

```bash
curl http://localhost:8000/documents
```

Manual validation with Docker:

```bash
echo "This is a sample company policy document." > sample.txt

curl -X POST http://localhost:8000/documents/upload \
  -F "file=@sample.txt"

# Use the returned id:
curl http://localhost:8000/documents/<returned-id>
```

> The original file is saved under `storage/uploads/` on the host (mounted into the container at `/app/storage/uploads`).

## Chunking

After uploading, trigger chunking to split the document text into overlapping character-based chunks and persist them in PostgreSQL.

**Parameters:** chunk size = 500 characters, overlap = 50 characters.

**Overlap example:**

```
Chunk 1: characters   0–499
Chunk 2: characters 450–949
Chunk 3: characters 900–1399
```

Each chunk overlaps the previous by 50 characters so context is preserved at boundaries. Chunking is idempotent — running it again replaces existing chunks.

Chunk a document:

```bash
curl -X POST http://localhost:8000/documents/<document-id>/chunk
```

Retrieve chunks:

```bash
curl http://localhost:8000/documents/<document-id>/chunks
```

Manual validation with Docker:

```sql
-- Check document status and chunk count
SELECT id, filename, status, chunk_count
FROM documents;

-- Inspect chunks
SELECT chunk_index, token_count, LEFT(content, 80)
FROM document_chunks
ORDER BY chunk_index;
```

Expected after chunking: `status = chunked`, `chunk_count > 0`.

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
| POST | `/documents/upload` | Upload a document (`.txt`, `.md`, `.pdf`) |
| POST | `/documents/{id}/chunk` | Chunk a document and persist to PostgreSQL |
| GET | `/documents/{id}/chunks` | List chunks with previews and token counts |
| GET | `/documents/{id}` | Get document metadata by UUID |
| GET | `/documents` | List all documents |

## Roadmap

| PR | Scope |
|---|---|
| PR 1 | Project skeleton, health endpoint, config |
| PR 2 | Docker Compose for API, PostgreSQL, ChromaDB |
| PR 3 | Database models, SQLAlchemy, Alembic migrations |
| PR 4 | Document upload, text extraction, file storage |
| PR 5 (this) | Text chunking, chunk persistence in PostgreSQL |
| PR 6 | Embeddings with sentence-transformers + ChromaDB storage |
| PR 7 | Ollama integration, RAG query endpoint |
| PR 7 | Conversation history, session management |
| PR 8 | Frontend UI (optional) |
