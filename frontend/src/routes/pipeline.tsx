import { createFileRoute } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Upload, FileText, Scissors, Sparkles, Database, Search, MessageSquare, ArrowRight } from "lucide-react";

export const Route = createFileRoute("/pipeline")({
  head: () => ({ meta: [{ title: "Pipeline — Enterprise Knowledge Assistant" }] }),
  component: PipelinePage,
});

const stages = [
  { icon: Upload, title: "Upload", body: "PDF, TXT, MD ingested into object storage.", phase: "Ingest" },
  { icon: FileText, title: "Extract Text", body: "PyMuPDF / unstructured parses pages and metadata.", phase: "Ingest" },
  { icon: Scissors, title: "Chunk", body: "Recursive splitter with 512-token windows and 64-token overlap.", phase: "Prepare" },
  { icon: Sparkles, title: "Embed", body: "sentence-transformers/all-MiniLM-L6-v2 to 384-dim vectors.", phase: "Prepare" },
  { icon: Database, title: "Store", body: "ChromaDB collection per workspace, persisted on disk.", phase: "Prepare" },
  { icon: Search, title: "Retrieve", body: "Top-k cosine similarity with MMR re-ranking.", phase: "Serve" },
  { icon: MessageSquare, title: "Generate", body: "LLM call with retrieved context and citation enforcement.", phase: "Serve" },
];

const phaseColor: Record<string, string> = {
  Ingest: "text-primary",
  Prepare: "text-accent",
  Serve: "text-[var(--color-success)]",
};

function PipelinePage() {
  return (
    <AppShell>
      <PageHeader
        eyebrow="System Design"
        title="RAG Pipeline"
        description="How a document becomes a grounded answer — from upload to generation."
      />
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="rounded-2xl border border-border bg-card/60 p-6 md:p-8">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            {stages.map((s, i) => (
              <div key={s.title} className="relative">
                <div className="rounded-xl border border-border bg-background/40 p-4 h-full">
                  <div className={`text-[10px] uppercase tracking-widest ${phaseColor[s.phase]}`}>{s.phase}</div>
                  <div className="mt-2 grid h-9 w-9 place-items-center rounded-md bg-secondary text-primary">
                    <s.icon className="h-4 w-4" />
                  </div>
                  <div className="mt-3 text-sm font-medium">{s.title}</div>
                  <div className="mt-1 text-xs text-muted-foreground leading-relaxed">{s.body}</div>
                </div>
                {i < stages.length - 1 && (
                  <ArrowRight className="hidden lg:block absolute -right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                )}
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Indexing throughput</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">1.2k <span className="text-sm font-normal text-muted-foreground">chunks/min</span></div>
          </div>
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Retrieval p95</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">284 <span className="text-sm font-normal text-muted-foreground">ms</span></div>
          </div>
          <div className="rounded-xl border border-border bg-card p-5">
            <div className="text-xs uppercase tracking-widest text-muted-foreground">Groundedness</div>
            <div className="mt-2 text-2xl font-semibold tabular-nums">98.2<span className="text-sm font-normal text-muted-foreground">%</span></div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}