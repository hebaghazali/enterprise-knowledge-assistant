# Enterprise Knowledge Assistant

A local-first, zero-cost Generative AI backend that lets you upload documents and ask questions against them using a fully local stack — no cloud APIs, no per-token costs.

## What this project does (eventually)

- Accept document uploads (PDF, text, etc.)
- Chunk and embed documents using local sentence-transformers
- Store vectors in ChromaDB
- Answer user questions with context retrieved from uploaded documents
- Use a locally running LLM via Ollama for generation
- Expose a conversational REST API via FastAPI

## Current scope (PR 8)

Single-turn grounded answer generation via Ollama:

- **`POST /answer`** — accepts a question, retrieves top-k relevant chunks, builds a grounded prompt, calls a local Ollama model, returns the answer with source citations
- Every answer request is logged in the `llm_runs` table (provider, model, prompt, response, latency, status)
- All previous endpoints remain unchanged

PR 7: Semantic retrieval with `GET /search`, vector indexing with ChromaDB.
PR 6: Embeddings with sentence-transformers + ChromaDB storage.
PR 5: Text chunking, chunk persistence in PostgreSQL.
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

## Grounded Answer Generation

The `/answer` endpoint retrieves relevant chunks and sends them as context to a local Ollama model. The model is instructed to answer only using retrieved context and to say "I don't know based on the provided documents." when the answer is not present.

### Prerequisites

Install and start Ollama:

```bash
ollama serve
ollama pull llama3.1:8b
```

For a lighter model (less RAM, slightly lower quality):

```bash
ollama pull llama3.2:3b
```

Then set `OLLAMA_MODEL=llama3.2:3b` in `.env`.

### Example

```bash
curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"How many remote days per week are employees allowed?\",\"k\":5}"
```

Expected response:

```json
{
  "question": "How many remote days per week are employees allowed?",
  "answer": "Employees may work remotely up to three days per week.",
  "sources": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "filename": "novatech_enterprise_handbook.txt",
      "chunk_index": 1,
      "similarity_score": 0.8421,
      "content_preview": "REMOTE WORK POLICY\n\nEmployees may work remotely up to three days per week..."
    }
  ],
  "model": "llama3.1:8b",
  "k": 5
}
```

### Notes

- This is **single-turn Q&A only** — no conversation history.
- **Streaming is not implemented** — the full answer is returned in one response.
- Answers are **grounded in retrieved chunks** — the model is blocked from inventing facts.
- Every request is logged in the `llm_runs` table for observability.
- Conversation history will be added in a later PR.

### Docker note

When running via Docker Compose, Ollama must be running on the host machine. The API container is pre-configured to reach it at `http://host.docker.internal:11434`.

### Verify LLM run logging

```sql
SELECT provider, model_name, status, latency_ms, created_at
FROM llm_runs
ORDER BY created_at DESC;
```

## Semantic Retrieval

User questions are converted into embeddings and matched against vectorized chunks stored in ChromaDB.

```bash
curl "http://localhost:8000/search?q=password+rules&k=3"
```

Flow:

```
Question
↓
Token-length check (≤ 512 tokens — rejects very long pasted prompts with 422)
↓
Embedding (sentence-transformers/all-MiniLM-L6-v2) — query embedded as a single vector
↓
Vector Search (ChromaDB cosine similarity)
↓
Top-K Chunks
```

Example response:

```json
{
  "query": "password rules",
  "results": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "filename": "policy.txt",
      "chunk_index": 2,
      "content": "Employees must follow password security rules...",
      "token_count": 87,
      "similarity_score": 0.8333
    }
  ],
  "result_count": 1
}
```

Similarity scores use `1 / (1 + distance)` — range [0, 1], higher means more similar.

**Query length limit:** Queries are embedded directly as a single vector. The MVP intentionally rejects very long pasted prompts (default maximum: 512 tokens) with a `422` error rather than silently truncating or chunking them. The limit is configurable via `MAX_QUERY_TOKENS` in `.env`. Future versions may support query decomposition or multi-query retrieval for longer inputs.

This PR implements retrieval only. It does NOT generate answers.

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
| GET | `/search?q=...&k=5` | Semantic search across all indexed chunks |
| POST | `/answer` | Ask a question — returns grounded answer + sources |

## Roadmap

| PR | Scope |
|---|---|
| PR 1 | Project skeleton, health endpoint, config |
| PR 2 | Docker Compose for API, PostgreSQL, ChromaDB |
| PR 3 | Database models, SQLAlchemy, Alembic migrations |
| PR 4 | Document upload, text extraction, file storage |
| PR 5 | Text chunking, chunk persistence in PostgreSQL |
| PR 6 | Embeddings with sentence-transformers + ChromaDB storage |
| PR 7 | Semantic retrieval with ChromaDB vector search |
| PR 8 (this) | Grounded answer generation via local Ollama |
| PR 9 | Conversation history, multi-turn chat sessions |
