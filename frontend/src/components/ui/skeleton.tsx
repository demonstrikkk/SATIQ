import { cn } from "@/lib/utils";

export function Skeleton({ className, ...p }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("relative overflow-hidden rounded-md bg-[#101827] skeleton-shimmer", className)} {...p} />;
}

export function TextSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="space-y-2.5 py-1">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={cn("h-3", i === 0 ? "w-[72%]" : i === lines - 1 ? "w-[58%]" : "w-full")} style={{ animationDelay: `${i * 90}ms` }} />
      ))}
    </div>
  );
}

export function ChartSkeleton() {
  return (
    <div className="my-4 rounded-xl border border-slate-700/40 bg-[#101827] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="px-4 py-2.5 border-b border-slate-700/40 bg-[#0B1120] flex items-center justify-between">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="h-3 w-12" />
      </div>
      <div className="h-[180px] w-full p-4 flex items-end gap-2 bg-[#05080F]">
        {[0.55, 0.82, 0.42, 0.68, 0.35].map((h, i) => (
          <Skeleton key={i} className="flex-1 rounded-t-md" style={{ height: `${h * 100}%`, animationDelay: `${i * 110}ms` }} />
        ))}
      </div>
      <div className="px-3 py-2 flex gap-1.5 border-t border-slate-700/40 bg-[#0B1120]">
        <Skeleton className="h-5 w-20 rounded-full" />
        <Skeleton className="h-5 w-24 rounded-full" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
    </div>
  );
}

export function TableSkeleton({ rows = 3, cols = 3 }: { rows?: number; cols?: number }) {
  return (
    <div className="my-4 overflow-hidden rounded-xl border border-slate-700/40 bg-[#101827]" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="grid" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0,1fr))` }}>
        {Array.from({ length: cols }).map((_, i) => (
          <div key={i} className="px-3.5 py-2.5 border-b border-slate-700/40 bg-[#0B1120]">
            <Skeleton className="h-3 w-16" />
          </div>
        ))}
        {Array.from({ length: rows * cols }).map((_, i) => (
          <div key={i} className="px-3.5 py-2.5 border-b border-slate-800/40">
            <Skeleton className="h-3 w-[70%]" style={{ animationDelay: `${(i % cols) * 70}ms` }} />
          </div>
        ))}
      </div>
    </div>
  );
}

export function MapSkeleton() {
  return (
    <div className="my-4 rounded-xl border border-amber-500/20 bg-amber-500/[0.04] overflow-hidden">
      <div className="px-3.5 py-2.5 border-b border-amber-500/20 flex items-center gap-2">
        <Skeleton className="h-3 w-28 bg-amber-500/20" />
        <Skeleton className="h-3 w-8 ml-auto bg-amber-500/10" />
      </div>
      <div className="h-[180px] w-full bg-gradient-to-br from-[#0F1A2E] to-[#14223A] relative overflow-hidden">
        <Skeleton className="absolute inset-0 rounded-none opacity-60" />
        <div className="absolute left-[22%] top-[28%] h-[34%] w-[28%] rounded-lg border-2 border-amber-400/30 bg-amber-400/10 animate-pulse" />
        <div className="absolute right-[18%] top-[42%] h-[22%] w-[20%] rounded-lg border-2 border-amber-400/20 bg-amber-400/5 animate-pulse" style={{ animationDelay: "400ms" }} />
      </div>
    </div>
  );
}

export function ComparisonSkeleton() {
  return (
    <div className="my-4 rounded-xl border border-slate-700/40 bg-[#101827] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="px-3.5 py-2.5 border-b border-slate-700/40 bg-[#0B1120] flex items-center gap-2">
        <Skeleton className="h-3 w-32" />
      </div>
      <div className="p-3 grid grid-cols-2 gap-2.5 bg-[#05080F]">
        <Skeleton className="aspect-video rounded-lg" />
        <Skeleton className="aspect-video rounded-lg" style={{ animationDelay: "120ms" }} />
      </div>
    </div>
  );
}

export function ImageSkeleton() {
  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700/40 bg-[#101827]" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <Skeleton className="aspect-[16/9] w-full rounded-none" />
      <div className="px-3 py-2 flex gap-2 border-t border-slate-700/40 bg-[#0B1120]">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-3 w-16 ml-auto" />
      </div>
    </div>
  );
}

// --- Scoped skeletons per STRICT spec §5 ---

export function PipelineStepSkeleton() {
  return (
    <div className="h-[52px] flex items-center gap-3 rounded-xl border border-slate-700/40 bg-[#101827] px-3 shrink-0">
      <Skeleton className="h-6 w-6 rounded-full shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-24" />
        <Skeleton className="h-2 w-32" />
      </div>
      <Skeleton className="h-3 w-16" />
    </div>
  );
}

export function ImageCardSkeleton({ aspectRatio = "16/9" }: { aspectRatio?: "16/9" | "4/3" | "1/1" }) {
  const ratioClass = aspectRatio === "4/3" ? "aspect-[4/3]" : aspectRatio === "1/1" ? "aspect-square" : "aspect-[16/9]";
  return (
    <div className="my-3 rounded-xl overflow-hidden border border-slate-700/40 bg-[#101827]" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <Skeleton className={`${ratioClass} w-full rounded-none`} />
      <div className="px-3 py-2 flex gap-2 bg-[#0B1120] border-t border-slate-700/40">
        <Skeleton className="h-3 w-20" />
      </div>
    </div>
  );
}

export function MessageTypingIndicator() {
  return (
    <div className="flex items-center gap-2 py-2">
      <span className="text-xs font-medium tracking-wide text-slate-500">Thinking</span>
      <span className="flex gap-1.5">
        <span className="typing-dot" style={{ animationDelay: "0ms" }} />
        <span className="typing-dot" style={{ animationDelay: "150ms" }} />
        <span className="typing-dot" style={{ animationDelay: "300ms" }} />
      </span>
    </div>
  );
}
