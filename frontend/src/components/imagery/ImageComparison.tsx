import * as React from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { SatCanvas } from "@/components/imagery/SatImageryCanvas";

export function ImageComparison({ className }: { className?: string }) {
  const [pos, setPos] = React.useState(50);
  const handleRef = React.useRef<HTMLDivElement>(null);
  const frameRef = React.useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = React.useState(false);

  const setPct = (pct: number) => setPos(Math.max(2, Math.min(98, pct)));

  React.useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging || !frameRef.current) return;
      const r = frameRef.current.getBoundingClientRect();
      setPct(((e.clientX - r.left) / r.width) * 100);
    };
    const onUp = () => setDragging(false);
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [dragging]);

  return (
    <div ref={frameRef} className={cn("relative aspect-[16/9] rounded-xl overflow-hidden border border-slate-700/40 bg-[#0b0f0d] group", className)}>
      {/* base after 2024 — growth 0.85 */}
      <SatCanvas mode="optical" seed={11} growth={0.85} className="absolute inset-0 h-full w-full" />
      <div className="absolute right-2 top-2 rounded-[3px] bg-[rgba(10,12,11,0.65)] px-1.5 py-0.5 text-[9.5px] font-mono uppercase tracking-[0.06em] text-slate-300">2024</div>
      {/* before clipped 2022 — growth 0.15 */}
      <div className="absolute inset-0 overflow-hidden" style={{ width: `${pos}%` }}>
        <SatCanvas mode="optical" seed={11} growth={0.15} className="h-full w-full" />
        <div className="absolute left-2 top-2 rounded-[3px] bg-[rgba(10,12,11,0.65)] px-1.5 py-0.5 text-[9.5px] font-mono uppercase tracking-[0.06em] text-slate-300">2022</div>
      </div>
      {/* divider — html .compare-handle */}
      <div
        ref={handleRef}
        className="absolute inset-y-0 w-0.5 bg-[#06B6D4] cursor-ew-resize"
        style={{ left: `${pos}%` }}
        onMouseDown={() => setDragging(true)}
        role="slider"
        aria-label="Comparison slider"
        aria-valuenow={pos}
      >
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-[26px] w-[26px] rounded-full bg-[#06B6D4] shadow-[0_0_0_4px_rgba(10,12,11,0.5)] grid place-items-center">
          <span className="text-[11px] font-bold text-white">⇔</span>
        </div>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={pos}
        onChange={e => setPos(Number(e.target.value))}
        className="absolute bottom-3 left-3 right-3 h-1 accent-[#06B6D4] opacity-0 group-hover:opacity-100 transition-opacity"
        aria-label="Comparison slider"
      />
    </div>
  );
}

export function SplitViewer({ leftLabel = "Optical (Sentinel-2)", rightLabel = "SAR (Sentinel-1)" }: { leftLabel?: string; rightLabel?: string }) {
  return (
    <div className="grid grid-cols-2 gap-px bg-[rgba(51,65,85,0.35)] p-px rounded-xl overflow-hidden">
      <div className="relative aspect-video overflow-hidden bg-[#0b0f0d]">
        <SatCanvas mode="optical" seed={11} growth={0.65} className="h-full w-full" />
        <div className="absolute bottom-1.5 left-1.5 rounded-full bg-[rgba(10,12,11,0.65)] px-2 py-1 text-[11px] font-medium text-white backdrop-blur">{leftLabel}</div>
        <div className="absolute top-1.5 right-1.5 rounded bg-[#06B6D4] text-white px-1.5 py-0.5 text-[10px] font-bold">82%</div>
      </div>
      <div className="relative aspect-video overflow-hidden bg-[#0b0f0d]">
        <SatCanvas mode="sar" seed={22} className="h-full w-full" />
        <div className="absolute bottom-1.5 left-1.5 rounded-full bg-[rgba(10,12,11,0.65)] px-2 py-1 text-[11px] font-medium text-white backdrop-blur">{rightLabel}</div>
        <div className="absolute top-1.5 right-1.5 rounded bg-slate-600 text-white px-1.5 py-0.5 text-[10px] font-bold">75%</div>
      </div>
    </div>
  );
}

export function ZoomableImage({ src, alt }: { src: string; alt?: string }) {
  const [loaded, setLoaded] = React.useState(false);
  const [open, setOpen] = React.useState(false);
  React.useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  return (
    <>
      <div className="rounded-xl overflow-hidden border border-[var(--color-border-subtle)] bg-[var(--color-surface-3)] my-3">
        <div className="relative aspect-[16/9] overflow-hidden bg-[var(--color-surface-2)] cursor-zoom-in group" onClick={() => setOpen(true)} role="button" aria-label={`View ${alt ?? "image"} large`}>
          {!loaded && <Skeleton className="absolute inset-0 rounded-none" />}
          <img src={src} alt={alt} onLoad={() => setLoaded(true)} className={cn("h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]", !loaded && "opacity-0")} loading="lazy" />
          <div className="absolute inset-0 bg-gradient-to-t from-black/20 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          <div className="absolute bottom-2 right-2 rounded-full bg-black/60 backdrop-blur border border-white/10 px-2.5 py-1 text-[11px] text-white flex items-center gap-1.5 shadow-md">
            Click to view large
          </div>
        </div>
        {alt && <div className="px-3 py-2 text-[11px] text-[var(--color-text-muted)] border-t border-[var(--color-border-subtle)] bg-[var(--color-surface-2)] truncate">{alt}</div>}
      </div>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 sm:p-6 bg-black/80 backdrop-blur-sm" onClick={() => setOpen(false)} role="dialog" aria-modal="true" aria-label={alt ? `Zoomed ${alt}` : "Zoomed image"}>
          <div className="relative max-w-[92vw] max-h-[88vh] w-auto flex flex-col items-center" onClick={(e) => e.stopPropagation()}>
            <img src={src} alt={alt} className="max-w-[92vw] max-h-[80vh] w-auto h-auto object-contain rounded-xl shadow-2xl border border-white/10" />
            {alt && <div className="mt-3 max-w-[90vw] text-sm text-white/90 text-center px-4 py-2 rounded-full bg-black/50 backdrop-blur border border-white/10 truncate">{alt}</div>}
            <button onClick={() => setOpen(false)} className="absolute -top-3 -right-3 h-9 w-9 rounded-full bg-white text-black grid place-items-center shadow-xl hover:bg-white/90 transition-colors border border-black/10" aria-label="Close">
              <span className="text-lg leading-none">×</span>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
