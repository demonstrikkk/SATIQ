import * as React from "react";
import { cn } from "@/lib/utils";
export function Progress({ value, className }: { value: number; className?: string }) {
  return <div className={cn("h-1.5 w-full rounded-full bg-[var(--color-surface-3)] border border-[var(--color-border-subtle)] overflow-hidden", className)}><div className="h-full bg-[var(--color-accent)] transition-all duration-500" style={{ width: `${Math.max(0,Math.min(100,value))}%`}} /></div>;
}
export function ConfidenceBar({ value, showLabel=true }: { value: number; showLabel?: boolean }) {
  const pct = Math.round(value*100);
  const tone = value>=0.9?"bg-emerald-500": value>=0.75?"bg-sky-500": value>=0.5?"bg-amber-500":"bg-red-500";
  return (
    <div className="space-y-1.5">
      <div className="h-1.5 w-full rounded-full bg-[var(--color-surface-3)] overflow-hidden border border-[var(--color-border-subtle)]"><div className={`h-full ${tone} transition-all`} style={{ width:`${pct}%`}}/></div>
      {showLabel && <div className="flex justify-between text-[11px] text-[var(--color-text-muted)]"><span>Confidence</span><span className="text-[var(--color-text-secondary)] font-medium">{pct}%</span></div>}
    </div>
  );
}
