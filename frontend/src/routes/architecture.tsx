import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Server, Database, Boxes, Sparkles, Container, BrainCircuit } from "lucide-react";

export const Route = createFileRoute("/architecture")({
  head: () => ({ meta: [{ title: "Architecture — Enterprise Knowledge Assistant" }] }),
  component: ArchitecturePage,
});

const stack = [
  { icon: Server, title: "FastAPI backend", tag: "API layer", body: "Async Python service exposing ingest, index, and query endpoints with Pydantic schemas and OpenAPI docs." },
  { icon: Database, title: "PostgreSQL metadata", tag: "Source of truth", body: "Stores documents, chunks, workspaces, users, and audit logs. SQLAlchemy plus Alembic migrations." },
  { icon: Boxes, title: "ChromaDB vector store", tag: "Retrieval", body: "Per-workspace collections, persistent on disk, cosine similarity with metadata filters." },
  { icon: Sparkles, title: "Sentence Transformers", tag: "Embeddings", body: "all-MiniLM-L6-v2 by default. Swap to instructor-xl or OpenAI embeddings via env vars." },
  { icon: Container, title: "Dockerized environment", tag: "DX", body: "docker-compose spins up API, Postgres, Chroma, and the frontend with one command." },
  { icon: BrainCircuit, title: "LLM integration", tag: "Roadmap", body: "Pluggable provider layer for OpenAI, Anthropic, and local models via vLLM or Ollama." },
];

function ArchitecturePage() {
  return (
    <AppShell>
      <PageHeader
        eyebrow="Under the hood"
        title="Technical architecture"
        description="The stack behind the assistant — designed to be replaceable, observable, and self-hostable."
      />
      <div className="mx-auto max-w-6xl px-6 py-10 space-y-8">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {stack.map((s) => (
            <div key={s.title} className="group rounded-xl border border-border bg-card p-6 hover:border-primary/40 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="grid h-10 w-10 place-items-center rounded-md" style={{ background: "var(--gradient-primary)" }}>
                  <s.icon className="h-5 w-5 text-primary-foreground" />
                </div>
                <span className="rounded-full border border-border bg-secondary px-2 py-0.5 text-[10px] uppercase tracking-widest text-muted-foreground">{s.tag}</span>
              </div>
              <div className="mt-4 font-medium">{s.title}</div>
              <div className="mt-1 text-sm text-muted-foreground leading-relaxed">{s.body}</div>
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-border bg-card/60 p-6 md:p-8">
          <div className="text-xs uppercase tracking-widest text-muted-foreground">High-level data flow</div>
          <pre className="mt-4 overflow-x-auto rounded-lg border border-border bg-background/60 p-4 text-xs leading-relaxed text-muted-foreground">
{`Frontend (React) ──▶ FastAPI services ──▶ PostgreSQL (metadata)
                          │                       
                          ▼                       
                  Sentence Transformers ──▶ ChromaDB (vectors)
                          │                       ▲
                          └──── retrieval ────────┘`}
          </pre>
        </div>
      </div>
    </AppShell>
  );
}