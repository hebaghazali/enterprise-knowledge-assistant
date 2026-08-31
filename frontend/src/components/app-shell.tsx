import { Link, useRouterState } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  LayoutDashboard,
  FileText,
  MessageSquare,
  GitBranch,
  Cpu,
  Sparkles,
  Search,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getDatabaseHealth, getHealth, getServiceInfo } from "@/lib/system-api";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/documents", label: "Documents", icon: FileText },
  { to: "/search", label: "Search", icon: Search },
  { to: "/ask", label: "Ask", icon: MessageSquare },
  { to: "/pipeline", label: "Pipeline", icon: GitBranch },
  { to: "/architecture", label: "Architecture", icon: Cpu },
] as const;

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const service = useQuery({
    queryKey: ["system", "info"],
    queryFn: getServiceInfo,
    staleTime: Infinity,
    retry: 1,
  });
  const apiHealth = useQuery({
    queryKey: ["system", "health"],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: 1,
  });
  const databaseHealth = useQuery({
    queryKey: ["system", "database"],
    queryFn: getDatabaseHealth,
    refetchInterval: 15_000,
    retry: 1,
  });

  const checking = apiHealth.isPending || databaseHealth.isPending;
  const apiOnline = apiHealth.data?.status === "ok";
  const databaseOnline =
    databaseHealth.data?.status === "ok" && databaseHealth.data.database === "connected";
  const status = checking
    ? { label: "Checking services…", className: "bg-[var(--color-warning)]" }
    : !apiOnline
      ? { label: "API unavailable", className: "bg-[var(--color-destructive)]" }
      : !databaseOnline
        ? { label: "Database unavailable", className: "bg-[var(--color-warning)]" }
        : { label: "All systems operational", className: "bg-[var(--color-success)]" };

  return (
    <div className="min-h-screen flex w-full bg-background">
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-border bg-card/40 backdrop-blur">
        <div className="px-6 py-6 border-b border-border">
          <Link to="/" className="flex items-center gap-2">
            <div
              className="grid h-9 w-9 place-items-center rounded-lg"
              style={{ background: "var(--gradient-primary)" }}
            >
              <Sparkles className="h-4 w-4 text-primary-foreground" />
            </div>
            <div className="min-w-0">
              <div className="text-sm font-semibold tracking-tight truncate">EKA</div>
              <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
                {service.data ? `API v${service.data.version}` : "Knowledge OS"}
              </div>
            </div>
          </Link>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {nav.map((item) => {
            const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
            const Icon = item.icon;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:bg-secondary/60 hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
        <div className="m-3 rounded-lg border border-border bg-card/60 p-3">
          <div className="text-xs font-medium">Status</div>
          <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
            <span className={cn("h-2 w-2 rounded-full", status.className)} />
            {status.label}
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="md:hidden flex items-center justify-between border-b border-border px-4 py-3 bg-card/40 backdrop-blur">
          <Link to="/" className="flex items-center gap-2">
            <div
              className="grid h-8 w-8 place-items-center rounded-md"
              style={{ background: "var(--gradient-primary)" }}
            >
              <Sparkles className="h-3.5 w-3.5 text-primary-foreground" />
            </div>
            <span className="text-sm font-semibold">EKA</span>
          </Link>
          <nav className="flex items-center gap-1 overflow-x-auto">
            {nav.map((item) => {
              const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  className={cn(
                    "rounded-md px-2.5 py-1.5 text-xs",
                    active ? "bg-secondary text-foreground" : "text-muted-foreground",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </header>
        <main className="flex-1 overflow-x-hidden">{children}</main>
      </div>
    </div>
  );
}
