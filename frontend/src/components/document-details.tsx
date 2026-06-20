import { useMemo } from "react";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { useIsMobile } from "@/hooks/use-mobile";
import { getDocumentDetails, type Document } from "@/lib/mock-api";
import {
  FileText,
  FileType2,
  FileCode2,
  Calendar,
  Layers,
  Download,
  RefreshCw,
  Sparkles,
  Database,
  CheckCircle2,
  Search,
  Hash,
} from "lucide-react";
import { cn } from "@/lib/utils";

function DocIcon({ type, className }: { type: Document["type"]; className?: string }) {
  const Icon = type === "PDF" ? FileType2 : type === "MD" ? FileCode2 : FileText;
  const tint =
    type === "PDF"
      ? "text-[oklch(0.7_0.18_25)] bg-[oklch(0.7_0.18_25_/_0.12)]"
      : type === "MD"
      ? "text-primary bg-primary/10"
      : "text-[var(--color-success)] bg-[oklch(0.72_0.13_160_/_0.12)]";
  return (
    <div className={cn("grid place-items-center rounded-lg", tint, className)}>
      <Icon className="h-5 w-5" />
    </div>
  );
}

function highlight(text: string, fragment: string) {
  if (!fragment) return text;
  const idx = text.toLowerCase().indexOf(fragment.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <mark className="rounded bg-primary/25 px-1 py-0.5 text-foreground">
        {text.slice(idx, idx + fragment.length)}
      </mark>
      {text.slice(idx + fragment.length)}
    </>
  );
}

function MetaItem({ icon: Icon, label, value }: { icon: React.ComponentType<{ className?: string }>; label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card/60 px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
        <Icon className="h-3 w-3" />
        {label}
      </div>
      <div className="mt-1 text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}

export function DocumentDetails({
  doc,
  open,
  onOpenChange,
}: {
  doc: Document | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const isMobile = useIsMobile();
  const details = useMemo(() => (doc ? getDocumentDetails(doc) : null), [doc]);

  if (!doc || !details) return null;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isMobile ? "bottom" : "right"}
        className={cn(
          "flex flex-col gap-0 border-border bg-background p-0 sm:max-w-none",
          isMobile ? "h-[100dvh] w-full rounded-none" : "h-full w-full sm:w-[640px] lg:w-[760px] xl:w-[860px]",
        )}
      >
        {/* Header */}
        <div className="shrink-0 border-b border-border bg-card/40 px-6 py-5">
          <div className="flex items-start gap-4">
            <DocIcon type={doc.type} className="h-11 w-11" />
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate text-base font-semibold">{doc.name}</SheetTitle>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <StatusBadge status={doc.status} />
                <span className="inline-flex items-center gap-1"><Calendar className="h-3 w-3" /> {doc.createdAt}</span>
                <span className="inline-flex items-center gap-1"><Layers className="h-3 w-3" /> {details.chunks.length.toLocaleString()} chunks</span>
                <span className="inline-flex items-center gap-1"><Hash className="h-3 w-3" /> {doc.type}</span>
              </div>
            </div>
            <div className="w-8" aria-hidden />
          </div>
        </div>

        {/* Body */}
        <div className="flex min-h-0 flex-1 flex-col">
          <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
            <div className="shrink-0 border-b border-border bg-card/20 px-6 pt-3">
              <TabsList className="bg-transparent p-0 h-auto gap-1">
                <TabsTrigger value="overview" className="data-[state=active]:bg-secondary rounded-md">Overview</TabsTrigger>
                <TabsTrigger value="chunks" className="data-[state=active]:bg-secondary rounded-md">Chunks</TabsTrigger>
                <TabsTrigger value="vector" className="data-[state=active]:bg-secondary rounded-md">Vector Index</TabsTrigger>
                <TabsTrigger value="retrieval" className="data-[state=active]:bg-secondary rounded-md">Retrieval Preview</TabsTrigger>
              </TabsList>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {/* Overview */}
              <TabsContent value="overview" className="mt-0 space-y-6">
                <section>
                  <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
                    <Sparkles className="h-3 w-3" /> AI Summary
                  </div>
                  <div
                    className="rounded-xl border border-border p-4 text-sm leading-relaxed"
                    style={{ background: "var(--gradient-hero, var(--gradient-primary))" }}
                  >
                    {details.summary}
                  </div>
                </section>

                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <MetaItem icon={Layers} label="Chunks" value={details.chunks.length.toLocaleString()} />
                  <MetaItem icon={Database} label="Vectors" value={details.vectorIndex.vectorCount.toLocaleString()} />
                  <MetaItem icon={Hash} label="Dim" value={details.vectorIndex.dimensions} />
                  <MetaItem icon={Calendar} label="Indexed" value={details.vectorIndex.indexedAt} />
                </div>

                <section>
                  <div className="mb-2 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
                      <FileText className="h-3 w-3" /> Extracted Text Preview
                    </div>
                    <span className="text-xs text-muted-foreground">{details.extractedText.length} sections</span>
                  </div>
                  <div className="rounded-xl border border-border bg-card/40">
                    <div className="max-h-[380px] space-y-4 overflow-y-auto p-5 text-sm leading-relaxed text-foreground/90">
                      {details.extractedText.map((p, i) => (
                        <p key={i} className="first-letter:text-base first-letter:font-semibold">{p}</p>
                      ))}
                    </div>
                  </div>
                </section>
              </TabsContent>

              {/* Chunks */}
              <TabsContent value="chunks" className="mt-0 space-y-3">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>{details.chunks.length} chunks generated · ~512 tokens target</span>
                  <span className="tabular-nums">
                    {details.chunks.reduce((s, c) => s + c.tokens, 0).toLocaleString()} tokens total
                  </span>
                </div>
                <div className="space-y-2.5">
                  {details.chunks.map((c) => (
                    <div key={c.index} className="group rounded-xl border border-border bg-card/40 p-4 transition-colors hover:border-primary/40 hover:bg-card/70">
                      <div className="mb-2 flex items-center justify-between text-xs">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-secondary px-1.5 font-mono text-[11px] font-semibold text-primary">
                            #{c.index}
                          </span>
                          <span className="text-muted-foreground">chunk_{String(c.index).padStart(4, "0")}</span>
                        </div>
                        <div className="flex items-center gap-3 text-muted-foreground tabular-nums">
                          <span>{c.chars.toLocaleString()} chars</span>
                          <span>·</span>
                          <span>~{c.tokens} tokens</span>
                        </div>
                      </div>
                      <p className="text-sm leading-relaxed text-foreground/85 line-clamp-3 group-hover:line-clamp-none">{c.text}</p>
                    </div>
                  ))}
                </div>
              </TabsContent>

              {/* Vector Index */}
              <TabsContent value="vector" className="mt-0 space-y-4">
                <div className="rounded-xl border border-border bg-card/40 p-5">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-sm font-semibold">Vector Index Status</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">Embeddings stored in your collection</div>
                    </div>
                    <span className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                      details.vectorIndex.indexed
                        ? "border-[var(--color-success)]/30 bg-[oklch(0.72_0.13_160_/_0.12)] text-[var(--color-success)]"
                        : "border-[var(--color-warning)]/30 bg-[oklch(0.78_0.14_75_/_0.12)] text-[var(--color-warning)]",
                    )}>
                      <CheckCircle2 className="h-3 w-3" />
                      {details.vectorIndex.indexed ? "Indexed" : "Pending"}
                    </span>
                  </div>

                  <dl className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {[
                      ["Embedding model", <code key="m" className="text-primary">{details.vectorIndex.model}</code>],
                      ["Collection", <code key="c" className="text-primary">{details.vectorIndex.collection}</code>],
                      ["Vectors", details.vectorIndex.vectorCount.toLocaleString()],
                      ["Dimensions", details.vectorIndex.dimensions],
                      ["Distance metric", "cosine"],
                      ["Indexed at", details.vectorIndex.indexedAt],
                    ].map(([label, value]) => (
                      <div key={String(label)} className="flex items-center justify-between rounded-lg border border-border/60 bg-background/50 px-3 py-2.5 text-sm">
                        <dt className="text-muted-foreground">{label}</dt>
                        <dd className="font-medium tabular-nums">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>

                <div className="rounded-xl border border-border bg-card/40 p-5">
                  <div className="mb-3 text-xs uppercase tracking-wider text-muted-foreground">Sample vector</div>
                  <div className="overflow-x-auto rounded-lg border border-border/60 bg-background/60 p-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
                    [{Array.from({ length: 8 }, (_, i) => (Math.sin(i * 1.7) * 0.5).toFixed(4)).join(", ")}, … {details.vectorIndex.dimensions - 8} more]
                  </div>
                </div>
              </TabsContent>

              {/* Retrieval */}
              <TabsContent value="retrieval" className="mt-0 space-y-4">
                <div className="rounded-xl border border-border bg-card/40 p-4">
                  <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-muted-foreground">
                    <Search className="h-3 w-3" /> Sample query
                  </div>
                  <div className="mt-2 flex items-center gap-3 rounded-lg border border-border/60 bg-background/60 px-3 py-2.5 text-sm">
                    <Search className="h-4 w-4 text-primary" />
                    <span className="font-medium">{details.retrieval.question}</span>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    Top {details.retrieval.hits.length} chunks retrieved from <code className="text-primary">{details.vectorIndex.collection}</code> in 184ms
                  </div>
                </div>

                <div className="space-y-2.5">
                  {details.retrieval.hits.map((hit, i) => (
                    <div key={i} className="rounded-xl border border-border bg-card/40 p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <div className="flex items-center gap-2 text-xs">
                          <span className="inline-flex h-6 items-center rounded-md bg-secondary px-2 font-mono font-semibold text-primary">
                            #{hit.chunkIndex}
                          </span>
                          <span className="text-muted-foreground">similarity</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 w-24 overflow-hidden rounded-full bg-secondary">
                            <div
                              className="h-full rounded-full"
                              style={{ width: `${Math.round(hit.score * 100)}%`, background: "var(--gradient-primary)" }}
                            />
                          </div>
                          <span className="w-12 text-right text-xs font-semibold tabular-nums text-primary">
                            {hit.score.toFixed(2)}
                          </span>
                        </div>
                      </div>
                      <p className="text-sm leading-relaxed text-foreground/90">
                        {highlight(hit.text, hit.highlight)}
                      </p>
                    </div>
                  ))}
                </div>
              </TabsContent>
            </div>
          </Tabs>
        </div>

        {/* Footer */}
        <div className="shrink-0 border-t border-border bg-card/40 px-6 py-3">
          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>Close</Button>
            <Button variant="outline" size="sm"><RefreshCw /> Re-chunk</Button>
            <Button variant="outline" size="sm"><Sparkles /> Re-index</Button>
            <Button size="sm"><Download /> Download</Button>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}