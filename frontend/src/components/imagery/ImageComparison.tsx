import * as React from "react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

export function ImageComparison({ className }: { className?: string }) {
  const [pos, setPos] = React.useState(50);
  const [loaded, setLoaded] = React.useState(false);
  const before = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450"><rect width="100%" height="100%" fill="#0D121F"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#475569" font-family="monospace" font-size="13">2018 · Sentinel-2 · 10 m</text></svg>');
  const after = "data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450"><rect width="100%" height="100%" fill="#090D14"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#475569" font-family="monospace" font-size="13">2023 · Sentinel-2 · 10 m</text></svg>');
  return (
    <div className={cn("relative aspect-[16/9] rounded-xl overflow-hidden border border-[var(--color-border-subtle)] bg-[var(--color-surface-3)] group", className)}>
      {!loaded && <Skeleton className="absolute inset-0 rounded-none" />}
      {/* base after */}
      <img src={after} alt="2023" onLoad={() => setLoaded(true)} className="absolute inset-0 h-full w-full object-cover" loading="lazy" style={{ filter: "contrast(1.05) saturate(0.85)" }} />
      <div className="absolute left-2 top-2 rounded-full bg-black/55 backdrop-blur border border-white/10 px-2 py-1 text-[11px] font-medium text-white">2023</div>
      {/* before clipped */}
      <div className="absolute inset-0 overflow-hidden" style={{ width: `${pos}%` }}>
        <img src={before} alt="2018" className="h-full w-full object-cover max-w-none" style={{ width: `${100 * (100 / Math.max(1, pos))}%`, filter: "contrast(1.05) saturate(0.9) brightness(0.95)" }} loading="lazy" />
        <div className="absolute left-2 top-2 rounded-full bg-black/55 backdrop-blur border border-white/10 px-2 py-1 text-[11px] font-medium text-white">2018</div>
      </div>
      {/* divider */}
      <div className="absolute inset-y-0 w-0.5 bg-white shadow-[0_0_8px_rgba(255,255,255,0.6)]" style={{ left: `${pos}%` }}>
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 h-7 w-7 rounded-full bg-white shadow-lg grid place-items-center border border-black/10">
          <span className="text-[10px] font-bold text-black">↔</span>
        </div>
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={pos}
        onChange={e => setPos(Number(e.target.value))}
        className="absolute bottom-3 left-3 right-3 h-1 accent-white opacity-80 group-hover:opacity-100 transition-opacity"
        aria-label="Comparison slider"
      />
    </div>
  );
}

export function SplitViewer({ leftLabel = "Optical (Sentinel-2)", rightLabel = "SAR (Sentinel-1)" }: { leftLabel?: string; rightLabel?: string }) {
  const [leftLoaded, setLeftLoaded] = React.useState(false);
  const [rightLoaded, setRightLoaded] = React.useState(false);
  return (
    <div className="grid grid-cols-2 gap-2.5">
      <div className="relative aspect-video rounded-xl overflow-hidden border border-[var(--color-border-subtle)] bg-[var(--color-surface-3)]">
        {!leftLoaded && <Skeleton className="absolute inset-0 rounded-none" />}
        <img src={"data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="340"><rect width="100%" height="100%" fill="#0D121F"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748B" font-family="monospace" font-size="12">Optical · Sentinel-2</text></svg>')} alt={leftLabel} onLoad={() => setLeftLoaded(true)} className="h-full w-full object-cover" loading="lazy" style={{ filter: "saturate(1.05) contrast(1.05)" }} />
        <div className="absolute bottom-1.5 left-1.5 rounded-full bg-black/60 backdrop-blur border border-white/10 px-2 py-1 text-[11px] font-medium text-white">{leftLabel}</div>
        <div className="absolute top-1.5 right-1.5 rounded-md bg-emerald-500 text-white px-1.5 py-0.5 text-[10px] font-bold">82%</div>
      </div>
      <div className="relative aspect-video rounded-xl overflow-hidden border border-[var(--color-border-subtle)] bg-[var(--color-surface-3)]">
        {!rightLoaded && <Skeleton className="absolute inset-0 rounded-none" />}
        <img src={"data:image/svg+xml;utf8," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="340"><rect width="100%" height="100%" fill="#090D14"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748B" font-family="monospace" font-size="12">SAR · Sentinel-1 · VV/VH</text></svg>')} alt={rightLabel} onLoad={() => setRightLoaded(true)} className="h-full w-full object-cover grayscale contrast-125" loading="lazy" />
        <div className="absolute bottom-1.5 left-1.5 rounded-full bg-black/60 backdrop-blur border border-white/10 px-2 py-1 text-[11px] font-medium text-white">{rightLabel}</div>
        <div className="absolute top-1.5 right-1.5 rounded-md bg-slate-600 text-white px-1.5 py-0.5 text-[10px] font-bold">75%</div>
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
