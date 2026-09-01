import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, Box, CheckCircle2, Cpu } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { PageHeader } from "@/components/page-header";
import { getConfiguredModel, listModels } from "@/lib/models-api";

export const Route = createFileRoute("/settings")({
  head: () => ({ meta: [{ title: "Settings — Enterprise Knowledge Assistant" }] }),
  component: SettingsPage,
});

function SettingsPage() {
  const configured = useQuery({
    queryKey: ["models", "configured"],
    queryFn: getConfiguredModel,
    refetchInterval: 15_000,
    retry: 1,
  });
  const models = useQuery({ queryKey: ["models"], queryFn: listModels, retry: 1 });

  return (
    <AppShell>
      <PageHeader
        eyebrow="Local inference"
        title="Model settings"
        description="Read-only visibility into the Ollama runtime. Configure models through environment variables and pull them explicitly from the CLI."
      />
      <div className="mx-auto max-w-5xl space-y-6 px-6 py-8">
        <div className="grid gap-4 md:grid-cols-2">
          <section className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Cpu className="h-4 w-4 text-primary" /> Configured model
            </div>
            <div className="mt-4 font-mono text-lg">
              {configured.data?.configured_model ?? "Checking…"}
            </div>
            <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
              {configured.data?.configured_model_present ? (
                <CheckCircle2 className="h-4 w-4 text-[var(--color-success)]" />
              ) : (
                <AlertCircle className="h-4 w-4 text-[var(--color-warning)]" />
              )}
              {configured.data?.configured_model_present
                ? "Installed and ready"
                : (configured.data?.detail ?? "Model is not installed")}
            </div>
            <div className="mt-2 text-xs text-muted-foreground">
              Ollama {configured.data?.version ?? "version unavailable"}
            </div>
          </section>

          <section className="rounded-xl border border-border bg-card p-6">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Box className="h-4 w-4 text-primary" /> Installed models
            </div>
            {models.isError ? (
              <p className="mt-4 text-sm text-[var(--color-destructive)]">{models.error.message}</p>
            ) : models.data?.models.length ? (
              <ul className="mt-4 space-y-2">
                {models.data.models.map((model) => (
                  <li key={model} className="rounded-md bg-secondary px-3 py-2 font-mono text-sm">
                    {model}
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-sm text-muted-foreground">No installed models found.</p>
            )}
          </section>
        </div>
        <div className="rounded-xl border border-border bg-card/60 p-5 text-sm text-muted-foreground">
          Set <code className="text-primary">OLLAMA_MODEL</code> in the root environment file. For
          Docker-managed Ollama, use the documented one-shot model pull command before asking
          questions.
        </div>
      </div>
    </AppShell>
  );
}
