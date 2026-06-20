import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, actions }: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="border-b border-border">
      <div className="mx-auto max-w-6xl px-6 py-10">
        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-end gap-4">
          <div className="min-w-0">
            {eyebrow && (
              <div className="text-xs uppercase tracking-widest text-muted-foreground">{eyebrow}</div>
            )}
            <h1 className="mt-2 text-3xl md:text-4xl font-semibold tracking-tight truncate">{title}</h1>
            {description && (
              <p className="mt-2 text-sm md:text-base text-muted-foreground max-w-2xl">{description}</p>
            )}
          </div>
          {actions && <div className="shrink-0 flex items-center gap-2">{actions}</div>}
        </div>
      </div>
    </div>
  );
}