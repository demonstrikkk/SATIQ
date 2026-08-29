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
          : "min-h-0 px-3.5 py-2.5 border border-slate-700/40 bg-[#101827] ring-1 ring-[#06B6D4]/10 shadow-sm",
        className
      )}
      style={variant === "user" ? { boxShadow: "0 2px 12px rgba(0,0,0,0.35)" } : undefined}
    >
      {children}
    </div>
  );
}

export function MessageCardSkeleton() {
  return (
    <div className="min-h-[120px] rounded-xl border border-slate-700/40 bg-[#101827] p-4 space-y-3" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="h-3 w-2/3 rounded bg-slate-700/40 skeleton-shimmer" />
      <div className="h-3 w-full rounded bg-slate-700/25 skeleton-shimmer" />
      <div className="h-3 w-5/6 rounded bg-slate-700/20 skeleton-shimmer" />
      <div className="flex gap-2 pt-1">
        <div className="h-6 w-24 rounded-full bg-slate-700/25 skeleton-shimmer" />
        <div className="h-6 w-20 rounded-full bg-slate-700/15 skeleton-shimmer" />
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
      className="inline-flex items-center gap-1.5 max-w-[180px] bg-[#101827] hover:bg-[#141F30] text-slate-400 hover:text-slate-200 rounded-full px-2.5 py-1 text-xs font-medium border border-slate-700/40 hover:border-slate-600/40 transition-colors shrink-0"
    >
      {icon}
      <span className="truncate max-w-[180px] inline-block align-middle">{children}</span>
    </button>
  );
}
