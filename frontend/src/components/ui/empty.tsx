import * as React from "react";
export function EmptyState({ icon, title, description, action }: { icon?: React.ReactNode; title: string; description?: string; action?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center text-center p-8 gap-3">
      {icon && <div className="text-[var(--color-text-faint)]">{icon}</div>}
      <div className="text-sm font-medium text-[var(--color-text-secondary)]">{title}</div>
      {description && <div className="text-xs text-[var(--color-text-muted)] max-w-[28ch]">{description}</div>}
      {action}
    </div>
  );
}
export function ErrorState({ message, onRetry }: { message: string; onRetry?: ()=>void }) {
  return (
    <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-300 flex items-center justify-between gap-3">
      <span>{message}</span>{onRetry && <button onClick={onRetry} className="text-xs underline">Retry</button>}
    </div>
  );
}
