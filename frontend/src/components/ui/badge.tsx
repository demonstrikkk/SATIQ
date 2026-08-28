import * as React from "react";
import { cn } from "@/lib/utils";
export function Badge({ className, ...p }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center rounded-full border border-[var(--color-border-subtle)] bg-[var(--color-surface-3)] px-2 py-0.5 text-[11px] font-medium text-[var(--color-text-secondary)]", className)} {...p} />;
}
export function StatusDot({ tone="accent", pulse=false, className="" }: { tone?: "accent"|"success"|"warning"|"danger"|"muted"; pulse?: boolean; className?: string }) {
  const map: Record<string,string> = { accent:"bg-[var(--color-accent)]", success:"bg-[var(--color-success)]", warning:"bg-[var(--color-warning)]", danger:"bg-[var(--color-danger)]", muted:"bg-[var(--color-text-muted)]"};
  return <span className={cn("inline-block h-2 w-2 rounded-full", map[tone], pulse && "animate-pulse", className)} />;
}
