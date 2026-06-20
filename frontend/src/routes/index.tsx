import { createFileRoute } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import { FileText, MessageSquare, Database, Layers, HelpCircle, Timer, ArrowRight, ShieldCheck, Zap, Quote } from "lucide-react";
import { mockMetrics } from "@/lib/mock-api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Enterprise Knowledge Assistant — Grounded answers from your documents" },
      { name: "description", content: "RAG-powered internal knowledge assistant. Upload documents, build a searchable knowledge base, and ask grounded questions with cited sources." },
      { property: "og:title", content: "Enterprise Knowledge Assistant" },
      { property: "og:description", content: "Upload documents, build a searchable knowledge base, and ask grounded questions with sources." },
    ],
  }),
  component: Index,
});

const metrics = [
  { label: "Documents Uploaded", value: mockMetrics.documents.toLocaleString(), icon: FileText, hint: "+12 this week" },
  { label: "Chunks Indexed", value: mockMetrics.chunks.toLocaleString(), icon: Layers, hint: "Across 6 collections" },
  { label: "Questions Answered", value: mockMetrics.questions.toLocaleString(), icon: HelpCircle, hint: "98.2% grounded" },
  { label: "Avg Retrieval Time", value: `${mockMetrics.avgRetrievalMs} ms`, icon: Timer, hint: "p95 under 300ms" },
];

function Index() {
  return (
    <AppShell>
      <section
        className="relative overflow-hidden border-b border-border"
        style={{ background: "var(--gradient-hero)" }}
      >
        <div
          className="absolute inset-0 opacity-30 pointer-events-none"
          style={{
            backgroundImage:
              "radial-gradient(800px 400px at 80% -10%, oklch(0.72 0.13 240 / 0.35), transparent), radial-gradient(600px 300px at 10% 110%, oklch(0.7 0.12 175 / 0.25), transparent)",
          }}
        />
        <div className="relative mx-auto max-w-6xl px-6 py-20 lg:py-28">
          <div className="inline-flex items-center gap-2 rounded-full border border-border bg-card/40 px-3 py-1 text-xs text-muted-foreground backdrop-blur">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-success)]" />
            RAG pipeline online · v0.4
          </div>
          <h1 className="mt-6 text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05]">
            Enterprise Knowledge<br />
            <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-accent)" }}>
              Assistant
            </span>
          </h1>
          <p className="mt-5 max-w-2xl text-base md:text-lg text-muted-foreground">
            Upload documents, build a searchable knowledge base, and ask grounded questions with cited
            sources — powered by retrieval-augmented generation over your private corpus.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg" className="shadow-[var(--shadow-glow)]">
              <Link to="/documents"><FileText /> Upload Document</Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/ask"><MessageSquare /> Ask a Question <ArrowRight /></Link>
            </Button>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 py-12">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {metrics.map((m) => (
            <div
              key={m.label}
              className="group relative overflow-hidden rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/40"
            >
              <div className="flex items-start justify-between">
                <div className="text-xs uppercase tracking-wider text-muted-foreground">{m.label}</div>
                <div className="grid h-8 w-8 place-items-center rounded-md bg-secondary text-primary">
                  <m.icon className="h-4 w-4" />
                </div>
              </div>
              <div className="mt-4 text-3xl font-semibold tracking-tight">{m.value}</div>
              <div className="mt-1 text-xs text-muted-foreground">{m.hint}</div>
              <div
                className="absolute inset-x-0 bottom-0 h-px opacity-0 transition-opacity group-hover:opacity-100"
                style={{ background: "var(--gradient-primary)" }}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { icon: ShieldCheck, title: "Grounded by design", body: "Every answer cites the exact chunks it came from, with similarity scores and source documents." },
            { icon: Zap, title: "Sub-200ms retrieval", body: "ChromaDB-backed vector search with sentence-transformer embeddings keeps latency low." },
            { icon: Database, title: "Bring your own corpus", body: "PDF, TXT, and Markdown. Ingest once, query forever — private to your workspace." },
          ].map((f) => (
            <div key={f.title} className="rounded-xl border border-border bg-card/60 p-6">
              <div className="grid h-10 w-10 place-items-center rounded-md bg-secondary text-primary">
                <f.icon className="h-5 w-5" />
              </div>
              <div className="mt-4 font-medium">{f.title}</div>
              <div className="mt-1 text-sm text-muted-foreground">{f.body}</div>
            </div>
          ))}
        </div>

        <div className="mt-10 rounded-2xl border border-border bg-card/60 p-8 md:p-10 relative overflow-hidden">
          <Quote className="absolute right-6 top-6 h-10 w-10 text-primary/20" />
          <div className="text-xs uppercase tracking-widest text-muted-foreground">Why teams choose EKA</div>
          <p className="mt-3 text-xl md:text-2xl font-medium leading-snug max-w-3xl">
            "We replaced three internal wikis with EKA. Onboarding time dropped 40%, and answers always
            link back to a source our engineers actually trust."
          </p>
          <div className="mt-4 text-sm text-muted-foreground">— Director of Engineering, Fortune 500 fintech</div>
        </div>
      </section>
    </AppShell>
  );
}
