import type { DocStatus } from "@/types/document";
import { cn } from "@/lib/utils";

const styles: Record<DocStatus, string> = {
  Uploaded:
    "bg-[oklch(0.78_0.14_75_/_0.12)]  text-[var(--color-warning)]     border-[var(--color-warning)]/30",
  Queued:
    "bg-[oklch(0.78_0.14_75_/_0.12)]  text-[var(--color-warning)]     border-[var(--color-warning)]/30",
  Processing:
    "bg-[oklch(0.72_0.13_280_/_0.12)] text-[oklch(0.72_0.13_280)]     border-[oklch(0.72_0.13_280)]/30",
  Chunked: "bg-[oklch(0.72_0.13_240_/_0.12)] text-primary                     border-primary/30",
  "Vector Indexed":
    "bg-[oklch(0.72_0.13_160_/_0.12)] text-[var(--color-success)]      border-[var(--color-success)]/30",
  Failed:
    "bg-[oklch(0.65_0.20_25_/_0.12)]  text-[var(--color-destructive)]  border-[var(--color-destructive)]/30",
};

export function StatusBadge({ status }: { status: DocStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium",
        styles[status],
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
    </span>
  );
}
