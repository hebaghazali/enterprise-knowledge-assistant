# Enterprise Knowledge Assistant

A local-first, zero-cost Generative AI backend that lets you upload documents and ask questions against them using a fully local stack — no cloud APIs, no per-token costs.

## What this project does (eventually)

- Accept document uploads (PDF, text, etc.)
- Chunk and embed documents using local sentence-transformers
- Store vectors in ChromaDB
- Answer user questions with context retrieved from uploaded documents
- Use a locally running LLM via Ollama for generation
- Expose a conversational REST API via FastAPI

## Current scope (PR 10)

Structured source citations in grounded answers:

- Prompt instructs the local LLM to cite facts inline using `[Source 1]`, `[Source 2]`, etc.
- `/answer` and `/conversations/{id}/messages` responses include a structured `citations` array
- Each citation carries `source_number`, `filename`, `chunk_id`, `document_id`, `chunk_index`, `similarity_score`, and a 300-character `content_preview`
- `sources` remains unchanged for backward compatibility (200-character preview)
- `llm_runs.run_metadata` now includes a `citations` summary (source number, chunk ID, filename)
- All previous endpoints and response fields remain unchanged

PR 9: Multi-turn conversational RAG with persistent conversation history.
PR 8: Grounded answer generation via Ollama with `POST /answer`.
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

## Local development

### Ports

| Service | URL |
|---|---|
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| Frontend | http://localhost:8080 (use the port printed by Vite) |
| ChromaDB | http://localhost:8001 |
| PostgreSQL | localhost:5432 |

### Backend (Docker — recommended)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
cp .env.example .env
docker compose up --build
```

### Frontend (local Vite/Nitro dev server)

Requires [Bun](https://bun.sh/).

```bash
cd frontend
cp .env.example .env
bun install
bun run dev
```

The frontend uses TanStack Start with Nitro as the SSR server. The dev server prints the actual port on startup; this project's Lovable Vite configuration currently uses `8080`.

`VITE_API_BASE_URL` in `frontend/.env` controls which backend the frontend calls. The default value (`http://localhost:8000`) points at the Docker Compose backend.

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

curl -X POST http://localhost:8000/documents/<returned-id>/chunk
curl -X POST http://localhost:8000/documents/<returned-id>/index

curl "http://localhost:8000/search?q=remote+work+policy&k=3"

curl -X POST http://localhost:8000/answer \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"How many remote days per week are employees allowed?\",\"k\":5}"
```

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

- **Streaming is not implemented** — the full answer is returned in one response.
- Answers are **grounded in retrieved chunks** — the model is blocked from inventing facts.
- Every request is logged in the `llm_runs` table for observability.
- For multi-turn conversations use the `/conversations` endpoints below.

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

**Limitation:** In this release, `citations` is derived directly from retrieved chunks rather than parsed from the generated answer. The model is instructed to cite only from the provided context, but whether each `[Source N]` in the answer exactly matches the citation list is not validated. Parsing and cross-referencing inline citations is planned for a future release.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/` | Project info |
| GET | `/health` | App process health (no DB dependency) |
| GET | `/health/db` | Database connectivity check |
| POST | `/documents/upload` | Upload a document (`.txt`, `.md`, `.pdf`) |
| POST | `/documents/{id}/chunk` | Chunk a document (token-based) and persist to PostgreSQL |
| POST | `/documents/{id}/index` | Generate embeddings and index a document's chunks into ChromaDB |
| GET | `/documents/{id}/chunks` | List chunks with previews and token counts |
| GET | `/documents/{id}` | Get document metadata by UUID |
| GET | `/documents` | List all documents |
| GET | `/search?q=...&k=5` | Semantic search across all indexed chunks |
| POST | `/answer` | Single-turn Q&A — grounded answer + sources (no history) |
| POST | `/conversations` | Create a new conversation session |
| GET | `/conversations/{id}` | Retrieve conversation metadata and message history |
| POST | `/conversations/{id}/messages` | Send a message — history-aware grounded answer + sources |

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
| PR 8 | Grounded answer generation via local Ollama |
| PR 9 | Conversation history, multi-turn chat sessions |
| PR 10 (this) | Structured source citations, citation rules in prompt |
