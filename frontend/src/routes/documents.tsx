import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { StatusBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Upload, FileText, Eye, Layers, Sparkles } from "lucide-react";
import { mockDocuments, type Document } from "@/lib/mock-api";
import { DocumentDetails } from "@/components/document-details";

export const Route = createFileRoute("/documents")({
  head: () => ({ meta: [{ title: "Documents — Enterprise Knowledge Assistant" }] }),
  component: DocumentsPage,
});

function DocumentsPage() {
  const [docs, setDocs] = useState<Document[]>(mockDocuments);
  const [dragging, setDragging] = useState(false);
  const [viewing, setViewing] = useState<Document | null>(null);

  const handleFiles = (files: FileList | null) => {
    if (!files) return;
    const newDocs: Document[] = Array.from(files).map((f) => ({
      id: crypto.randomUUID(),
      name: f.name,
      type: (f.name.split(".").pop()?.toUpperCase() as Document["type"]) ?? "TXT",
      status: "Uploaded",
      chunks: 0,
      createdAt: new Date().toISOString().slice(0, 10),
    }));
    setDocs((d) => [...newDocs, ...d]);
  };

  const advance = (id: string, status: Document["status"], chunks?: number) => {
    setDocs((d) => d.map((doc) => doc.id === id ? { ...doc, status, chunks: chunks ?? doc.chunks } : doc));
  };

  return (
    <AppShell>
      <PageHeader
        eyebrow="Knowledge Base"
        title="Documents"
        description="Upload PDF, TXT, or Markdown files. Each document is chunked and embedded into the vector store for retrieval."
      />
      <div className="mx-auto max-w-6xl px-6 py-8 space-y-8">
        <label
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
          className={`block cursor-pointer rounded-2xl border-2 border-dashed p-10 text-center transition-colors ${dragging ? "border-primary bg-primary/5" : "border-border bg-card/40 hover:border-primary/40"}`}
        >
          <input type="file" multiple accept=".pdf,.txt,.md" className="sr-only" onChange={(e) => handleFiles(e.target.files)} />
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl" style={{ background: "var(--gradient-primary)" }}>
            <Upload className="h-5 w-5 text-primary-foreground" />
          </div>
          <div className="mt-4 font-medium">Drop files or click to upload</div>
          <div className="mt-1 text-sm text-muted-foreground">PDF · TXT · Markdown — up to 50MB each</div>
        </label>

        <div className="rounded-xl border border-border bg-card overflow-hidden">
          <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center px-5 py-4 border-b border-border">
            <div>
              <div className="text-sm font-medium">All documents</div>
              <div className="text-xs text-muted-foreground">{docs.length} files in your workspace</div>
            </div>
            <Button variant="outline" size="sm"><Sparkles /> Re-index all</Button>
          </div>
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
                {docs.map((d) => (
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
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <DocumentDetails doc={viewing} open={!!viewing} onOpenChange={(o) => !o && setViewing(null)} />
    </AppShell>
  );
}