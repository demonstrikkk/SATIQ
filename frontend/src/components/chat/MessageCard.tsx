import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Message card per spec §5: 
 * User: right-aligned, #1E293B radius 14 padding 14 18
 * Assistant: #1E293B or transparent with subtle border, max 780 centered
 * Skeleton occupies exact min-height to prevent CLS pops
 */
export function MessageCard({
  children,
  variant = "assistant",
  className,
}: {
  children: ReactNode;
  variant?: "assistant" | "user";
  className?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-xl",
        variant === "assistant"
          ? "min-h-0 p-0 space-y-3 border-0 bg-transparent shadow-none"
          : "min-h-0 px-3.5 py-2.5 border border-slate-800/60 bg-[#0D121F] ring-1 ring-[#06B6D4]/10 shadow-sm",
        className
      )}
    >
      {children}
    </div>
  );
}

export function MessageCardSkeleton() {
  return (
    <div className="min-h-[120px] rounded-xl border border-slate-800/60 bg-[#0D121F] p-4 shadow-sm space-y-3">
      <div className="h-3 w-2/3 rounded bg-slate-800/60 skeleton-shimmer" />
      <div className="h-3 w-full rounded bg-slate-800/40 skeleton-shimmer" />
      <div className="h-3 w-5/6 rounded bg-slate-800/30 skeleton-shimmer" />
      <div className="flex gap-2 pt-1">
        <div className="h-6 w-24 rounded-lg bg-slate-800/30 skeleton-shimmer" />
        <div className="h-6 w-20 rounded-lg bg-slate-800/20 skeleton-shimmer" />
      </div>
    </div>
  );
}

export function ActionChip({
  children,
  onClick,
  icon,
}: {
  children: ReactNode;
  onClick?: () => void;
  icon?: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 max-w-[180px] bg-[#0D121F] hover:bg-slate-800/60 text-slate-400 hover:text-slate-200 rounded-lg px-2.5 py-1 text-xs font-mono border border-slate-800/60 transition-colors shrink-0"
    >
      {icon}
      <span className="truncate max-w-[180px] inline-block align-middle">{children}</span>
    </button>
  );
}
