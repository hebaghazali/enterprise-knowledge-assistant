import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Upload, FileText, Eye, Layers, Sparkles, AlertCircle } from "lucide-react";
import { DocumentDetails } from "@/components/document-details";
import { listDocuments, uploadDocument } from "@/lib/documents-api";
import type { Document } from "@/types/document";

export const Route = createFileRoute("/documents")({
  head: () => ({ meta: [{ title: "Documents — Enterprise Knowledge Assistant" }] }),
  component: DocumentsPage,
});

function DocumentsPage() {
  const [dragging, setDragging] = useState(false);
  const [viewing, setViewing] = useState<Document | null>(null);

  const queryClient = useQueryClient();

  const { data: docs = [], isLoading, isError, error } = useQuery({
    queryKey: ["documents"],
    queryFn: listDocuments,
    retry: 1,
  });

  const uploadMutation = useMutation({
    mutationFn: uploadDocument,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const handleFiles = async (files: FileList | null) => {
    if (!files) return;
    for (const file of Array.from(files)) {
      await uploadMutation.mutateAsync(file).catch(() => {});
    }
  };

  // Locally advance a document's status in the cache (used by mock Chunk/Index buttons).
  const advance = (id: string, status: Document["status"], chunks?: number) => {
    queryClient.setQueryData<Document[]>(["documents"], (prev) =>
      (prev ?? []).map((doc) =>
        doc.id === id ? { ...doc, status, chunks: chunks ?? doc.chunks } : doc
      )
    );
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Knowledge Base"
        title="Documents"
        description="Upload PDF, TXT, or Markdown files. Each document is chunked and embedded into the vector store for retrieval."
      />
      <div className="mx-auto max-w-6xl px-6 py-8 space-y-8">

        {/* Upload zone */}
        <label
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); void handleFiles(e.dataTransfer.files); }}
          className={`block cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${
            uploadMutation.isPending
              ? "pointer-events-none opacity-60"
              : dragging
              ? "border-primary bg-primary/5"
              : "border-border bg-card/40 hover:border-primary/40"
          }`}
        >
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md"
            className="sr-only"
            disabled={uploadMutation.isPending}
            onChange={(e) => { void handleFiles(e.target.files); }}
          />
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl" style={{ background: "var(--gradient-primary)" }}>
            <Upload className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="mt-4 font-medium">
            {uploadMutation.isPending ? "Uploading…" : "Drop files or click to upload"}
          </div>
          <div className="mt-1 text-sm text-muted-foreground">PDF · TXT · Markdown — up to 50MB each</div>
        </label>

        {/* Upload error */}
        {uploadMutation.isError && (
          <div className="flex items-start gap-3 rounded-xl border border-[var(--color-destructive)]/30 bg-[oklch(0.65_0.20_25_/_0.08)] px-4 py-3 text-sm text-[var(--color-destructive)]">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{uploadMutation.error instanceof Error ? uploadMutation.error.message : "Upload failed."}</span>
          </div>
        )}

        {/* Document table */}
        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center px-5 py-4 border-b border-border">
            <div>
              <div className="text-sm font-medium">All documents</div>
              <div className="text-xs text-muted-foreground">
                {isLoading ? "Loading…" : `${docs.length} files in your workspace`}
              </div>
            </div>
            <Button variant="outline" size="sm"><Sparkles /> Re-index all</Button>
          </div>

          {/* Fetch error */}
          {isError && (
            <div className="flex items-start gap-3 border-b border-border px-5 py-4 text-sm text-[var(--color-destructive)]">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              <span>
                {error instanceof Error ? error.message : "Could not load documents."}
                {" "}<span className="text-muted-foreground">Check that the backend is running at {import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"}.</span>
              </span>
            </div>
          )}

          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border">
                  <th className="text-left font-medium px-5 py-3">File</th>
                  <th className="text-left font-medium px-3 py-3">Type</th>
                  <th className="text-left font-medium px-3 py-3">Status</th>
                  <th className="text-right font-medium px-3 py-3">Chunks</th>
                  <th className="text-left font-medium px-3 py-3">Created</th>
                  <th className="text-right font-medium px-5 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i} className="border-b border-border/60 last:border-0">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3">
                          <div className="h-8 w-8 shrink-0 rounded-md bg-muted animate-pulse" />
                          <div className="h-4 w-40 rounded bg-muted animate-pulse" />
                        </div>
                      </td>
                      <td className="px-3 py-3"><div className="h-4 w-8 rounded bg-muted animate-pulse" /></td>
                      <td className="px-3 py-3"><div className="h-5 w-20 rounded-full bg-muted animate-pulse" /></td>
                      <td className="px-3 py-3"><div className="h-4 w-6 rounded bg-muted animate-pulse ml-auto" /></td>
                      <td className="px-3 py-3"><div className="h-4 w-20 rounded bg-muted animate-pulse" /></td>
                      <td className="px-5 py-3"><div className="h-8 w-32 rounded bg-muted animate-pulse ml-auto" /></td>
                    </tr>
                  ))
                ) : docs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-12 text-center text-sm text-muted-foreground">
                      No documents yet. Upload a file above to get started.
                    </td>
                  </tr>
                ) : (
                  docs.map((d) => (
                    <tr key={d.id} className="border-b border-border/60 last:border-0 hover:bg-secondary/40">
                      <td className="px-5 py-3">
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-secondary text-primary">
                            <FileText className="h-4 w-4" />
                          </div>
                          <span className="truncate font-medium">{d.name}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-muted-foreground">{d.type}</td>
                      <td className="px-3 py-3"><StatusBadge status={d.status} /></td>
                      <td className="px-3 py-3 text-right tabular-nums">{d.chunks.toLocaleString()}</td>
                      <td className="px-3 py-3 text-muted-foreground">{d.createdAt}</td>
                      <td className="px-5 py-3">
                        <div className="flex justify-end gap-1">
                          <Button size="sm" variant="ghost" disabled={d.status !== "Uploaded"} onClick={() => advance(d.id, "Chunked", Math.floor(40 + Math.random() * 200))}>
                            <Layers /> Chunk
                          </Button>
                          <Button size="sm" variant="ghost" disabled={d.status !== "Chunked"} onClick={() => advance(d.id, "Vector Indexed")}>
                            <Sparkles /> Index
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => setViewing(d)}><Eye /> View</Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <DocumentDetails doc={viewing} open={!!viewing} onOpenChange={(o) => !o && setViewing(null)} />
    </AppShell>
  );
}
