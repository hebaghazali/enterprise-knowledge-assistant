import { useQuery } from "@tanstack/react-query";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { StatusBadge } from "@/components/status-badge";
import { useIsMobile } from "@/hooks/use-mobile";
import { getDocument, getDocumentChunks } from "@/lib/documents-api";
import type { Document } from "@/types/document";
import {
  AlertCircle,
  Calendar,
  CheckCircle2,
  FileCode2,
  FileText,
  FileType2,
  Hash,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";

function DocIcon({ type, className }: { type: Document["type"]; className?: string }) {
  const Icon = type === "PDF" ? FileType2 : type === "MD" ? FileCode2 : FileText;
  return (
    <div className={cn("grid place-items-center rounded-lg bg-secondary text-primary", className)}>
      <Icon className="h-5 w-5" />
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-card/60 px-3 py-2.5">
      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</div>
      <div className="mt-1 break-words text-sm font-medium tabular-nums">{value}</div>
    </div>
  );
}

function displayDate(value: string | undefined) {
  return value ? new Date(value).toLocaleString() : "Not available";
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
  const documentId = doc?.id ?? "";
  const details = useQuery({
    queryKey: ["document", documentId, "details"],
    queryFn: () => getDocument(documentId),
    enabled: open && Boolean(documentId),
    retry: 1,
  });
  const chunks = useQuery({
    queryKey: ["document", documentId, "chunks"],
    queryFn: () => getDocumentChunks(documentId),
    enabled: open && Boolean(documentId),
    retry: 1,
  });

  if (!doc) return null;

  const metadata = details.data?.metadata ?? {};
  const indexed = details.data?.status === "vector_indexed";
  const chunkItems = chunks.data?.chunks ?? [];
  const totalTokens = chunkItems.reduce((sum, chunk) => sum + (chunk.token_count ?? 0), 0);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isMobile ? "bottom" : "right"}
        className={cn(
          "flex flex-col gap-0 border-border bg-background p-0 sm:max-w-none",
          isMobile ? "h-[100dvh] w-full rounded-none" : "h-full w-full sm:w-[640px] lg:w-[760px]",
        )}
      >
        <div className="shrink-0 border-b border-border bg-card/40 px-6 py-5">
          <div className="flex items-start gap-4">
            <DocIcon type={doc.type} className="h-11 w-11" />
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate text-base font-semibold">{doc.name}</SheetTitle>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <StatusBadge status={doc.status} />
                <span className="inline-flex items-center gap-1">
                  <Calendar className="h-3 w-3" /> {doc.createdAt}
                </span>
                <span className="inline-flex items-center gap-1">
                  <Layers className="h-3 w-3" /> {chunks.data?.chunk_count ?? doc.chunks} chunks
                </span>
                <span className="inline-flex items-center gap-1">
                  <Hash className="h-3 w-3" /> {doc.type}
                </span>
              </div>
            </div>
            <div className="w-8" aria-hidden />
          </div>
        </div>

        <div className="flex min-h-0 flex-1 flex-col">
          {(details.isError || chunks.isError) && (
            <div className="m-6 flex items-start gap-2 rounded-lg border border-[var(--color-destructive)]/30 p-3 text-sm text-[var(--color-destructive)]">
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              {details.error instanceof Error
                ? details.error.message
                : chunks.error instanceof Error
                  ? chunks.error.message
                  : "Could not load document details."}
            </div>
          )}
          <Tabs defaultValue="overview" className="flex min-h-0 flex-1 flex-col">
            <div className="shrink-0 border-b border-border bg-card/20 px-6 pt-3">
              <TabsList className="h-auto gap-1 bg-transparent p-0">
                <TabsTrigger
                  value="overview"
                  className="rounded-md data-[state=active]:bg-secondary"
                >
                  Overview
                </TabsTrigger>
                <TabsTrigger value="chunks" className="rounded-md data-[state=active]:bg-secondary">
                  Chunks
                </TabsTrigger>
                <TabsTrigger value="vector" className="rounded-md data-[state=active]:bg-secondary">
                  Vector Index
                </TabsTrigger>
              </TabsList>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {details.isPending || chunks.isPending ? (
                <div className="rounded-xl border border-border bg-card/40 p-6 text-sm text-muted-foreground">
                  Loading document details…
                </div>
              ) : (
                <>
                  <TabsContent value="overview" className="mt-0 space-y-5">
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      <MetaItem
                        label="Content type"
                        value={details.data?.content_type ?? "Unknown"}
                      />
                      <MetaItem label="Source" value={details.data?.source_type ?? "Unknown"} />
                      <MetaItem
                        label="Text length"
                        value={details.data?.text_length?.toLocaleString() ?? "Unknown"}
                      />
                      <MetaItem
                        label="File size"
                        value={
                          typeof metadata.file_size_bytes === "number"
                            ? `${metadata.file_size_bytes.toLocaleString()} bytes`
                            : "Unknown"
                        }
                      />
                      <MetaItem label="Created" value={displayDate(details.data?.created_at)} />
                      <MetaItem label="Updated" value={displayDate(details.data?.updated_at)} />
                    </div>
                  </TabsContent>

                  <TabsContent value="chunks" className="mt-0 space-y-3">
                    <div className="flex items-center justify-between text-xs text-muted-foreground">
                      <span>{chunkItems.length} chunks generated</span>
                      <span>{totalTokens.toLocaleString()} tokens total</span>
                    </div>
                    {chunkItems.length === 0 ? (
                      <div className="rounded-xl border border-border p-6 text-sm text-muted-foreground">
                        This document has not been chunked yet.
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        {chunkItems.map((chunk) => (
                          <div
                            key={chunk.id}
                            className="rounded-xl border border-border bg-card/40 p-4"
                          >
                            <div className="mb-2 flex items-center justify-between text-xs">
                              <span className="rounded-md bg-secondary px-2 py-1 font-mono font-semibold text-primary">
                                #{chunk.chunk_index}
                              </span>
                              <span className="text-muted-foreground">
                                {chunk.token_count ?? "Unknown"} tokens
                              </span>
                            </div>
                            <p className="text-sm leading-relaxed text-foreground/85">
                              {chunk.content_preview}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="vector" className="mt-0 space-y-4">
                    <div className="rounded-xl border border-border bg-card/40 p-5">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="text-sm font-semibold">Vector Index Status</div>
                          <div className="mt-0.5 text-xs text-muted-foreground">
                            Embedding metadata reported by EKA
                          </div>
                        </div>
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                            indexed
                              ? "border-[var(--color-success)]/30 text-[var(--color-success)]"
                              : "border-border text-muted-foreground",
                          )}
                        >
                          <CheckCircle2 className="h-3 w-3" /> {indexed ? "Indexed" : "Pending"}
                        </span>
                      </div>
                      <div className="mt-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <MetaItem
                          label="Embedding model"
                          value={String(metadata.embedding_model ?? "Not indexed")}
                        />
                        <MetaItem
                          label="Collection"
                          value={String(metadata.chroma_collection ?? "Not indexed")}
                        />
                        <MetaItem
                          label="Vectors"
                          value={indexed ? chunkItems.length.toLocaleString() : "0"}
                        />
                        <MetaItem
                          label="Indexed at"
                          value={
                            typeof metadata.indexed_at === "string"
                              ? displayDate(metadata.indexed_at)
                              : "Not indexed"
                          }
                        />
                      </div>
                    </div>
                  </TabsContent>
                </>
              )}
            </div>
          </Tabs>
        </div>

        <div className="shrink-0 border-t border-border bg-card/40 px-6 py-3 text-right">
          <Button variant="ghost" size="sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
