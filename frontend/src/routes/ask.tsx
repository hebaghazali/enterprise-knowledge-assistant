import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Send, Sparkles, FileText, Timer, ShieldCheck } from "lucide-react";
import { askQuestion, type AnswerResponse } from "@/lib/mock-api";

export const Route = createFileRoute("/ask")({
  head: () => ({ meta: [{ title: "Ask — Enterprise Knowledge Assistant" }] }),
  component: AskPage,
});

const suggestions = [
  "What is our paid time off policy?",
  "Summarize the Q1 financial highlights.",
  "How do I onboard a new engineer?",
  "What are the data retention rules?",
];

function AskPage() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState<AnswerResponse | null>(null);

  const submit = async (text?: string) => {
    const query = (text ?? q).trim();
    if (!query) return;
    setQ(query);
    setLoading(true);
    setAnswer(null);
    const res = await askQuestion(query);
    setAnswer(res);
    setLoading(false);
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Retrieval-Augmented Generation"
        title="Ask your knowledge base"
        description="Questions are answered from indexed documents only. Every response includes the chunks that grounded it."
      />

      <div className="mx-auto max-w-6xl px-6 py-8 space-y-6">
        <form
          onSubmit={(e) => { e.preventDefault(); submit(); }}
          className="rounded-xl border border-border bg-card p-2 flex items-center gap-2 focus-within:border-primary/60 transition-colors"
        >
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-md text-primary">
            <Sparkles className="h-4 w-4" />
          </div>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ask a question about your knowledge base…"
            className="flex-1 min-w-0 bg-transparent py-2 text-base outline-none placeholder:text-muted-foreground"
          />
          <Button type="submit" disabled={loading || !q.trim()}>
            {loading ? "Thinking…" : <>Ask <Send /></>}
          </Button>
        </form>

        {!answer && !loading && (
          <div>
            <div className="text-xs uppercase tracking-widest text-muted-foreground mb-2">Try asking</div>
            <div className="flex flex-wrap gap-2">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => submit(s)}
                  className="rounded-full border border-border bg-card px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground hover:border-primary/40 transition-colors"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="rounded-xl border border-border bg-card p-6 animate-pulse text-muted-foreground">
            Retrieving top chunks and generating a grounded answer…
          </div>
        )}

        {answer && (
          <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
            <div className="space-y-4 min-w-0">
              <div className="rounded-xl border border-border bg-card p-6">
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-[var(--color-success)]" /> Groundedness {Math.round(answer.groundedness * 100)}%</span>
                  <span className="inline-flex items-center gap-1.5"><Timer className="h-3.5 w-3.5" /> {answer.latencyMs} ms</span>
                  <span className="inline-flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" /> {answer.sources.length} sources</span>
                </div>
                <div className="mt-4 text-[15px] leading-relaxed">{answer.answer}</div>
                <div className="mt-5 h-1.5 w-full rounded-full bg-secondary overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${answer.groundedness * 100}%`, background: "var(--gradient-accent)" }} />
                </div>
              </div>

              <div className="rounded-xl border border-border bg-card p-6">
                <div className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Source citations</div>
                <ul className="space-y-3">
                  {answer.sources.map((s, i) => (
                    <li key={i} className="rounded-lg border border-border bg-background/40 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2 min-w-0">
                          <FileText className="h-4 w-4 shrink-0 text-primary" />
                          <span className="truncate text-sm font-medium">{s.document}</span>
                        </div>
                        {s.page && <span className="text-xs text-muted-foreground shrink-0">p. {s.page}</span>}
                      </div>
                      <div className="mt-2 text-sm text-muted-foreground italic">"{s.snippet}"</div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <aside className="rounded-xl border border-border bg-card p-5 h-fit lg:sticky lg:top-6">
              <div className="text-xs uppercase tracking-widest text-muted-foreground">Retrieved context</div>
              <div className="mt-1 text-sm font-medium">Top {answer.chunks.length} matched chunks</div>
              <ul className="mt-4 space-y-3">
                {answer.chunks.map((c) => (
                  <li key={c.id} className="rounded-lg border border-border bg-background/40 p-3">
                    <div className="flex items-center justify-between gap-2 text-xs">
                      <span className="truncate text-muted-foreground">{c.document}</span>
                      <span className="shrink-0 rounded bg-secondary px-1.5 py-0.5 tabular-nums text-primary">{c.score.toFixed(2)}</span>
                    </div>
                    <div className="mt-2 text-xs leading-relaxed text-muted-foreground line-clamp-3">{c.preview}</div>
                  </li>
                ))}
              </ul>
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  );
}