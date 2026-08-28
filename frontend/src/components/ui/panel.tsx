import * as React from "react";
import { cn } from "@/lib/utils";
export function Panel({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-[var(--color-border-subtle)] bg-[var(--color-surface-2)] overflow-hidden", className)} {...p} />;
}
export function PanelHeader({ title, subtitle, actions, icon }: { title: string; subtitle?: string; actions?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-[var(--color-border-subtle)] bg-[var(--color-surface-1)]/60">
      <div className="flex items-center gap-2">
        {icon && <span className="text-[var(--color-text-muted)]">{icon}</span>}
        <div>
          <div className="text-xs font-semibold tracking-widest uppercase text-[var(--color-text-secondary)]">{title}</div>
          {subtitle && <div className="text-[11px] text-[var(--color-text-muted)]">{subtitle}</div>}
        </div>
      </div>
      {actions}
    </div>
  );
}
export function Divider({ className }: { className?: string }) { return <div className={cn("h-px bg-[var(--color-border-subtle)]", className)} />; }
