# Enterprise Knowledge Assistant

A local-first, zero-cost knowledge assistant that lets you upload documents and ask cited questions using a fully local stack — no cloud APIs or per-token costs.

## What this project does

- Accept document uploads (PDF, text, etc.)
- Chunk and embed documents using local sentence-transformers
- Store vectors in ChromaDB
- Answer user questions with context retrieved from uploaded documents
- Use a locally running LLM via Ollama for generation
- Expose a conversational REST API via FastAPI

## Current capabilities

- Upload, delete, chunk, and index PDF, Markdown, and text documents.
- Durable PostgreSQL-backed ingestion jobs with progress and retry.
- Semantic retrieval through sentence-transformers and ChromaDB.
- Buffered and streaming grounded answers through local Ollama.
- Persistent multi-turn conversations and structured source citations.
- Dependency-level readiness checks and read-only model visibility.
- A containerized frontend and same-origin private-LAN gateway.

## Tech stack

| Layer | Tool |
|---|---|
| API | FastAPI |
| Relational DB | PostgreSQL |
| Vector DB | ChromaDB |
| LLM | Ollama (local) |
| Embeddings | sentence-transformers |
| ORM | SQLAlchemy + Alembic |
| Job queue | PostgreSQL (`SKIP LOCKED`) |
| Containerisation | Docker Compose |
| Testing | pytest + httpx |

## Local development

### Unified local stack

Native Ollama is recommended on macOS so it can use Apple hardware acceleration:

```bash
ollama serve
ollama pull llama3.1:8b
cp .env.example .env
docker compose up --build
```

Open `http://localhost:8080`. The API and Swagger UI are available through
`http://localhost:8080/api` and `http://localhost:8080/api/docs`.

For a lighter model, run `ollama pull llama3.2:3b` and set
`OLLAMA_MODEL=llama3.2:3b` in `.env`.

On Linux, make the native Ollama listener reachable from Docker by starting it
with `OLLAMA_HOST=0.0.0.0:11434` on a trusted machine.

### Docker-managed Ollama

The project never downloads a model implicitly. Start Ollama, explicitly pull
the configured model, then start the complete stack:

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d ollama
docker compose -f docker-compose.yml -f docker-compose.ollama.yml --profile tools run --rm ollama-pull
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up --build
```

### Development ports

The base stack exposes only the gateway. Add the development override when
direct access to service ports is useful:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

| Service | URL |
|---|---|
| Unified app | http://localhost:8080 |
| Backend API (development override) | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend (development override) | http://localhost:3000 |
| ChromaDB (development override) | http://localhost:8001 |
| PostgreSQL (development override) | localhost:5432 |

### Backend development

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

### Frontend (local Vite/Nitro dev server)

Requires [Bun](https://bun.sh/).

```bash
cd frontend
cp .env.example .env
bun install
bun run dev
```

The frontend uses TanStack Start with Nitro as the SSR server. The development
server prints its actual port on startup.

`VITE_API_BASE_URL` in `frontend/.env` controls which backend the frontend calls. The default value (`http://localhost:8000`) points at the Docker Compose backend.

Compose runs database migrations automatically before starting the API and worker.
To apply migrations manually during backend-only development:

```bash
docker compose exec api alembic upgrade head
```

Test the running API:

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/health/db
curl http://localhost:8000/health/chroma
curl http://localhost:8000/health/ollama
curl http://localhost:8000/health/ready
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

### Sample documents

The `samples/` directory contains ready-to-upload `.txt` files for manual testing of the full upload → chunk → index → search/answer pipeline:

| File | Contents |
|---|---|
| `samples/enterprise_knowledge_assistant_test_document.txt` | Long synthetic document describing this project's own architecture (upload, chunking, embeddings, ChromaDB, retrieval) — useful for testing chunk boundaries and retrieval quality. |
| `samples/novatech_enterprise_handbook.txt` | Fictional company handbook: remote work policy, PTO/leave, security requirements, engineering standards, deployment/incident response procedures, on-call rotations, AWS infrastructure overview, data retention, new hire FAQs. |
| `samples/novatech_product_operations_knowledge_base.txt` | Fictional product/ops knowledge base: product catalog, pricing rules, customer tiers, business continuity (RTO/RPO), backup schedules, vendor policies, escalation matrices. |

Example using the handbook:

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@samples/novatech_enterprise_handbook.txt"

curl -X POST http://localhost:8000/documents/<returned-id>/process
curl http://localhost:8000/jobs/<returned-job-id>

curl "http://localhost:8000/search?q=remote+work+policy&k=3"

curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"How many remote days per week are employees allowed?\",\"k\":5}"
```

The `process` endpoint is the normal path. It returns HTTP 202 and the worker
durably moves the job through `extracting`, `chunking`, `embedding`,
`indexing`, and `completed`. The separate `/chunk` and `/index` endpoints are
retained for compatibility and troubleshooting.

## Chunking

After uploading, trigger chunking to split the document text into overlapping **token-based** chunks and persist them in PostgreSQL.

**Parameters:** chunk size = 500 tokens, overlap = 50 tokens — tokenized with the `sentence-transformers/all-MiniLM-L6-v2` WordPiece tokenizer (the same tokenizer used for embeddings).

Chunk boundaries are computed from token character-offsets and sliced directly out of the *original* text rather than reconstructed from decoded tokens, so casing, punctuation, and spacing are preserved exactly as written. Each chunk is lightly cleaned before storage — decorative separator lines (`====`, `----`, `____`) are stripped, repeated whitespace is collapsed, and excess blank lines are reduced — without altering wording or punctuation.

**Overlap example** (9 tokens, chunk_size=5, chunk_overlap=2, step=3):

```
Chunk 1: tokens 0–4
Chunk 2: tokens 3–7  (2-token overlap with chunk 1)
Chunk 3: tokens 6–8  (2-token overlap with chunk 2)
```

Chunking is idempotent — running it again deletes existing chunks for the document and replaces them.

Chunk a document:

```bash
curl -X POST http://localhost:8000/documents/<document-id>/chunk
```

Optional query params: `chunk_size` (default 500), `chunk_overlap` (default 50, must be less than `chunk_size`).

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

## Embeddings & Vector Indexing

After chunking, index a document to generate embeddings and store them in ChromaDB for semantic search.

Embeddings are generated with `sentence-transformers/all-MiniLM-L6-v2` (lazy-loaded once per process; model weights are cached under `~/.cache/huggingface`).

Index a document:

```bash
curl -X POST http://localhost:8000/documents/<document-id>/index
```

Indexing is **selective**: only chunks that haven't been indexed yet, or were indexed into a different Chroma collection, are embedded. Already-indexed chunks are skipped, so re-running indexing after adding new chunks doesn't redo unchanged work.

Example response:

```json
{
  "document_id": "...",
  "status": "vector_indexed",
  "chunk_count": 12,
  "indexed_chunk_count": 12,
  "skipped_chunk_count": 0,
  "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
  "chroma_collection": "enterprise_knowledge_chunks"
}
```

Each chunk is stored in ChromaDB with metadata: `document_id`, `chunk_id`, `chunk_index`, `filename`, `token_count`.

Expected after indexing: `status = vector_indexed`.

> If you change the chunking or cleanup logic and want to fully re-embed existing documents, re-run `/chunk` (which deletes and regenerates chunks, clearing their `chroma_id`) before re-indexing — otherwise indexing will skip chunks it already considers up to date.

## Private-LAN operation and storage

The gateway is suitable for a trusted private network only. It does not add
authentication or public TLS. Other devices on the LAN can use
`http://<host-ip>:8080`; do not expose that port to the public internet.

Persistent state is stored in these locations:

| Data | Location |
|---|---|
| Uploaded source files | `storage/uploads/` on the host |
| PostgreSQL records | `postgres_data` Docker volume |
| Chroma vectors | `chroma_data` Docker volume |
| Embedding model cache | `hf_cache` Docker volume |
| Docker-managed Ollama models | `ollama_data` Docker volume |

For a consistent backup, stop the API and worker, dump PostgreSQL with
`pg_dump`, copy `storage/uploads/`, and snapshot the named Chroma and Ollama
volumes. The database, uploaded files, and vector store belong to one logical
backup and should be restored together.

Stop services without deleting data:

```bash
docker compose down
```

To permanently remove PostgreSQL, Chroma, and model-cache volumes, use
`docker compose down -v`. Add both Ollama Compose files when removing the
Docker-managed Ollama volume. This cannot be undone without a backup.

## Local setup (without Docker)

`pyproject.toml` and `uv.lock` are the authoritative Python dependency files.
Install the locked development environment with uv:

```bash
uv sync --frozen --extra dev
cp .env.example .env
```

Run the API:

```bash
uv run uvicorn app.main:app --reload
```

The API will be available at `http://localhost:8000`.

Interactive docs: `http://localhost:8000/docs`

## Running tests

```bash
uv run --frozen --extra dev pytest
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
  "answer": "Employees may work remotely up to three days per week. [Source 1]",
  "citations": [
    {
      "source_number": 1,
      "chunk_id": "...",
      "document_id": "...",
      "filename": "novatech_enterprise_handbook.txt",
      "chunk_index": 1,
      "similarity_score": 0.8421,
      "content_preview": "REMOTE WORK POLICY\n\nEmployees may work remotely up to three days per week..."
    }
  ],
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

- `/answer` remains available for buffered responses; `/answer/stream` sends
  `sources`, `token`, `complete`, and `error` SSE events over a POST response.
- Answers are **grounded in retrieved chunks** — the model is blocked from inventing facts.
- Every request is logged in the `llm_runs` table for observability.
- For multi-turn conversations use the `/conversations` endpoints below.

### Docker note

The base Compose file reaches a native host Ollama at
`http://host.docker.internal:11434`. Add `docker-compose.ollama.yml` to run
Ollama in Docker instead. In both cases, model pulls are explicit.

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

## Conversation Support

Conversations persist multi-turn chat history. Each new message loads the last 10 messages from the conversation, injects them into the prompt, and generates an answer grounded in retrieved document chunks.

### Create a conversation

```bash
curl -X POST http://localhost:8000/conversations
```

Response:

```json
{
  "conversation_id": "...",
  "created_at": "2026-06-20T12:00:00Z"
}
```

### Send a message

```bash
curl -X POST http://localhost:8000/conversations/<conversation-id>/messages \
  -H "Content-Type: application/json" \
  -d "{\"message\": \"How many remote days are employees allowed?\", \"k\": 5}"
```

Response:

```json
{
  "conversation_id": "...",
  "message_id": "...",
  "answer": "Employees may work remotely up to three days per week. [Source 1]",
  "citations": [
    {
      "source_number": 1,
      "chunk_id": "...",
      "document_id": "...",
      "filename": "novatech_enterprise_handbook.txt",
      "chunk_index": 1,
      "similarity_score": 0.8421,
      "content_preview": "REMOTE WORK POLICY\n\nEmployees may work remotely..."
    }
  ],
  "sources": [
    {
      "chunk_id": "...",
      "document_id": "...",
      "filename": "novatech_enterprise_handbook.txt",
      "chunk_index": 1,
      "similarity_score": 0.8421,
      "content_preview": "REMOTE WORK POLICY\n\nEmployees may work remotely..."
    }
  ]
}
```

### Retrieve conversation history

```bash
curl http://localhost:8000/conversations/<conversation-id>
```

Response:

```json
{
  "conversation_id": "...",
  "created_at": "...",
  "messages": [
    {"message_id": "...", "role": "user", "content": "How many remote days?", "created_at": "..."},
    {"message_id": "...", "role": "assistant", "content": "Three days per week.", "created_at": "..."}
  ]
}
```

### How it works

```
POST /conversations/{id}/messages
  ↓  validate message (400/422)
  ↓  look up conversation (404 if missing)
  ↓  load last 10 messages as history
  ↓  store user message
  ↓  retrieve top-k chunks from ChromaDB
  ↓  build prompt: system rules + conversation history + question + context
  ↓  call Ollama
  ↓  store assistant message
  ↓  log llm_run (linked to conversation_id)
  ↓  return answer + sources
```

The prompt places conversation history after the grounding rules and before the retrieved context. The model is still instructed to answer only from retrieved chunks — history provides conversational continuity, not a second knowledge source.

### Verify conversation logging

```sql
SELECT c.id, COUNT(m.id) AS message_count
FROM conversations c
LEFT JOIN messages m ON m.conversation_id = c.id
GROUP BY c.id
ORDER BY c.created_at DESC;

SELECT conversation_id, status, latency_ms
FROM llm_runs
WHERE conversation_id IS NOT NULL
ORDER BY created_at DESC;
```

## Source Citations

Retrieved chunks are numbered as Source 1, Source 2, etc. in retrieval order. The prompt instructs the local LLM to cite facts inline using those numbers (e.g. `[Source 1]`, `[Source 1], [Source 2]`). The API also returns structured citation metadata so clients can display source previews and links alongside the answer.

Each citation in the response contains:

| Field | Description |
|---|---|
| `source_number` | Position in retrieval order, starting at 1 |
| `filename` | Originating document filename |
| `chunk_id` | Unique chunk identifier |
| `document_id` | Parent document identifier |
| `chunk_index` | Position of this chunk within the document |
| `similarity_score` | Cosine similarity score [0, 1] |
| `content_preview` | First 300 characters of the chunk text |

The `sources` field is retained unchanged (200-character preview) for backward compatibility.

The answer pipeline treats `k` as a retrieval ceiling and removes candidates
whose similarity score is not close to the best match before generation. The
margin is configurable with `ANSWER_RELEVANCE_SCORE_MARGIN` (default `0.05`).
The `sources` field reports the context sent to the model, while `citations`
contains only `[Source N]` references present in the completed answer. A
supported single-source answer receives a deterministic source reference if a
small local model omits the requested inline citation.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Project info |
| GET | `/health` | App process health (no DB dependency) |
| GET | `/health/db` | Database connectivity check |
| GET | `/health/chroma` | ChromaDB connectivity check |
| GET | `/health/ollama` | Ollama and configured-model readiness |
| GET | `/health/ready` | Aggregate required-service readiness |
| POST | `/documents/upload` | Upload a document (`.txt`, `.md`, `.pdf`) |
| POST | `/documents/{id}/chunk` | Chunk a document (token-based) and persist to PostgreSQL |
| POST | `/documents/{id}/index` | Generate embeddings and index a document's chunks into ChromaDB |
| GET | `/documents/{id}/chunks` | List chunks with previews and token counts |
| GET | `/documents/{id}` | Get document metadata by UUID |
| GET | `/documents` | List all documents |
| DELETE | `/documents/{id}` | Delete a document, file, chunks, and vectors |
| POST | `/documents/{id}/process` | Queue durable chunking and indexing work |
| GET | `/documents/{id}/jobs` | List recent ingestion jobs |
| GET | `/jobs/{id}` | Get ingestion progress and status |
| POST | `/jobs/{id}/retry` | Retry a failed or cancelled ingestion job |
| GET | `/search?q=...&k=5` | Semantic search across all indexed chunks |
| POST | `/answer` | Single-turn Q&A — grounded answer + sources (no history) |
| POST | `/answer/stream` | Streaming single-turn Q&A over SSE |
| POST | `/conversations` | Create a new conversation session |
| GET | `/conversations/{id}` | Retrieve conversation metadata and message history |
| POST | `/conversations/{id}/messages` | Send a message — history-aware grounded answer + sources |
| POST | `/conversations/{id}/messages/stream` | Stream a history-aware answer over SSE |
| GET | `/models` | List installed Ollama models and runtime status |
| GET | `/models/configured` | Inspect the configured model |

## Continuous integration

The CI workflow gates backend lint and tests, frontend lint, typechecking,
tests and production build, Alembic head validation, and every supported
Compose configuration. The integration suite uses real PostgreSQL and Chroma
with deterministic embeddings and a mocked Ollama; a real-Ollama smoke test is
opt-in so CI never downloads models implicitly.
