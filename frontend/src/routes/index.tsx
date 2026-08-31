import { createFileRoute } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AppShell } from "@/components/app-shell";
import { Button } from "@/components/ui/button";
import {
  FileText,
  MessageSquare,
  Database,
  Layers,
  ArrowRight,
  ShieldCheck,
  Search,
  Server,
} from "lucide-react";
import { listDocuments } from "@/lib/documents-api";
import { getServiceInfo } from "@/lib/system-api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Enterprise Knowledge Assistant — Grounded answers from your documents" },
      {
        name: "description",
        content:
          "RAG-powered internal knowledge assistant. Upload documents, build a searchable knowledge base, and ask grounded questions with cited sources.",
      },
      { property: "og:title", content: "Enterprise Knowledge Assistant" },
      {
        property: "og:description",
        content:
          "Upload documents, build a searchable knowledge base, and ask grounded questions with sources.",
      },
    ],
  }),
  component: Index,
});

function Index() {
  const documents = useQuery({ queryKey: ["documents"], queryFn: listDocuments, retry: 1 });
  const service = useQuery({
    queryKey: ["system", "info"],
    queryFn: getServiceInfo,
    staleTime: Infinity,
    retry: 1,
  });
  const docs = documents.data ?? [];
  const metrics = [
    {
      label: "Documents",
      value: documents.isPending ? "—" : docs.length.toLocaleString(),
      icon: FileText,
      hint: "Uploaded files",
    },
    {
      label: "Chunks",
      value: documents.isPending
        ? "—"
        : docs.reduce((sum, doc) => sum + doc.chunks, 0).toLocaleString(),
      icon: Layers,
      hint: "Generated across documents",
    },
    {
      label: "Indexed",
      value: documents.isPending
        ? "—"
        : docs.filter((doc) => doc.status === "Vector Indexed").length.toLocaleString(),
      icon: Database,
      hint: "Ready for retrieval",
    },
    {
      label: "API Version",
      value: service.data?.version ?? "—",
      icon: Server,
      hint: service.data?.name ?? "Backend unavailable",
    },
  ];

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
            <span
              className={`h-1.5 w-1.5 rounded-full ${service.data ? "bg-[var(--color-success)]" : "bg-[var(--color-warning)]"}`}
            />
            {service.data
              ? `${service.data.name} · v${service.data.version}`
              : "Connecting to EKA API…"}
          </div>
          <h1 className="mt-6 text-4xl md:text-6xl font-semibold tracking-tight leading-[1.05]">
            Enterprise Knowledge
            <br />
            <span
              className="bg-clip-text text-transparent"
              style={{ backgroundImage: "var(--gradient-accent)" }}
            >
              Assistant
            </span>
          </h1>
          <p className="mt-5 max-w-2xl text-base md:text-lg text-muted-foreground">
            Upload documents, build a searchable knowledge base, and ask grounded questions with
            cited sources — powered by retrieval-augmented generation over your private corpus.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button asChild size="lg" className="shadow-[var(--shadow-glow)]">
              <Link to="/documents">
                <FileText /> Upload Document
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline">
              <Link to="/ask">
                <MessageSquare /> Ask a Question <ArrowRight />
              </Link>
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
                <div className="text-xs uppercase tracking-wider text-muted-foreground">
                  {m.label}
                </div>
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
            {
              icon: ShieldCheck,
              title: "Grounded by design",
              body: "Every answer cites the exact chunks it came from, with similarity scores and source documents.",
            },
            {
              icon: Search,
              title: "Semantic retrieval",
              body: "Search indexed document chunks and inspect their similarity scores and source context.",
            },
            {
              icon: Database,
              title: "Bring your own corpus",
              body: "PDF, TXT, and Markdown. Ingest once, query forever — private to your workspace.",
            },
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
      </section>
    </AppShell>
  );
}
