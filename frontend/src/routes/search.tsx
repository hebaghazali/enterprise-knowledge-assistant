import { createFileRoute } from "@tanstack/react-router";
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { AlertCircle, FileText, Hash, Search } from "lucide-react";
import { searchKnowledge } from "@/lib/search-api";

export const Route = createFileRoute("/search")({
  head: () => ({ meta: [{ title: "Search — Enterprise Knowledge Assistant" }] }),
  component: SearchPage,
});

function SearchPage() {
  const [query, setQuery] = useState("");
  const [k, setK] = useState(5);
  const search = useMutation({
    mutationFn: ({ query, k }: { query: string; k: number }) => searchKnowledge(query, k),
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    const value = query.trim();
    if (value) search.mutate({ query: value, k });
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Semantic Retrieval"
        title="Search the knowledge base"
        description="Find the most similar chunks across every indexed document."
      />
      <div className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <form
          onSubmit={submit}
          className="flex flex-col gap-3 rounded-xl border border-border bg-card p-3 sm:flex-row"
        >
          <div className="flex min-w-0 flex-1 items-center gap-3 px-2">
            <Search className="h-4 w-4 shrink-0 text-primary" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search indexed documents…"
              className="min-w-0 flex-1 bg-transparent py-2 outline-none placeholder:text-muted-foreground"
            />
          </div>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            Results
            <select
              value={k}
              onChange={(event) => setK(Number(event.target.value))}
              className="h-9 rounded-md border border-border bg-background px-2 text-sm text-foreground"
            >
              {Array.from({ length: 10 }, (_, index) => index + 1).map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <Button type="submit" disabled={!query.trim() || search.isPending}>
            <Search /> {search.isPending ? "Searching…" : "Search"}
          </Button>
        </form>

        {search.isError && (
          <div className="flex items-start gap-2 rounded-xl border border-[var(--color-destructive)]/30 p-4 text-sm text-[var(--color-destructive)]">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            {search.error instanceof Error ? search.error.message : "Search failed."}
          </div>
        )}

        {search.data && (
          <section>
            <div className="mb-3 flex items-center justify-between text-sm">
              <span className="font-medium">Results for “{search.data.query}”</span>
              <span className="text-muted-foreground">{search.data.result_count} matches</span>
            </div>
            {search.data.results.length === 0 ? (
              <div className="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
                No matching chunks were found. Try a broader query or index more documents.
              </div>
            ) : (
              <div className="space-y-3">
                {search.data.results.map((result) => (
                  <article
                    key={result.chunk_id}
                    className="rounded-xl border border-border bg-card p-5"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-2">
                        <FileText className="h-4 w-4 shrink-0 text-primary" />
                        <span className="truncate text-sm font-medium">{result.filename}</span>
                        <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                          <Hash className="h-3 w-3" />
                          {result.chunk_index}
                        </span>
                      </div>
                      <span className="rounded-md bg-secondary px-2 py-1 text-xs font-semibold tabular-nums text-primary">
                        {result.similarity_score.toFixed(3)} similarity
                      </span>
                    </div>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-foreground/85">
                      {result.content}
                    </p>
                    <div className="mt-3 text-xs text-muted-foreground">
                      {result.token_count ?? "Unknown"} tokens
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        )}
      </div>
    </AppShell>
  );
}
