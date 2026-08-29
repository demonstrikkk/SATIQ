import { useEffect, useState } from "react";
import { X, Maximize2, Download, Copy, ZoomIn, ZoomOut, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";

export type LightboxImage = {
  src: string;
  alt: string;
  label?: string;
  bbox?: [number, number, number, number] | null;
  bboxLabel?: string | null;
  confidence?: number | null;
};

export function ChatImageLightbox({
  image,
  onClose,
}: {
  image: LightboxImage | null;
  onClose: () => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState<[number, number]>([0, 0]);
  const [dragging, setDragging] = useState(false);
  const [dragStart, setDragStart] = useState<[number, number]>([0, 0]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!image) return;
    setZoom(1);
    setOffset([0, 0]);
    setLoaded(false);
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(4, z + 0.25));
      if (e.key === "-") setZoom((z) => Math.max(0.5, z - 0.25));
      if (e.key === "0") { setZoom(1); setOffset([0, 0]); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [image, onClose]);

  useEffect(() => {
    if (image) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => { document.body.style.overflow = ""; };
  }, [image]);

  if (!image) return null;

  const bbox = image.bbox;

  return (
    <div
      className="fixed inset-0 z-[80] flex flex-col bg-black/85 backdrop-blur-md"
      role="dialog"
      aria-modal="true"
      aria-label={image.alt}
      onClick={onClose}
    >
      {/* Header */}
      <div className="h-[56px] shrink-0 flex items-center justify-between px-4 border-b border-white/10 bg-black/40" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-7 w-7 rounded-lg bg-white/10 border border-white/10 grid place-items-center shrink-0">
            <Maximize2 size={13} className="text-white" />
          </div>
          <div className="min-w-0">
            <div className="text-[13px] font-semibold text-white truncate leading-none">{image.label || image.alt}</div>
            <div className="text-[11px] text-white/60 truncate">10 m GSD · EPSG:32617 · {bbox ? "bbox overlay enabled" : "full frame"} · {Math.round(zoom * 100)}%</div>
          </div>
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg bg-white/10 border border-white/10 text-white hover:bg-white/15" onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))} aria-label="Zoom out">
            <ZoomOut size={14} />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg bg-white/10 border border-white/10 text-white hover:bg-white/15" onClick={() => { setZoom(1); setOffset([0, 0]); }} aria-label="Reset zoom">
            <RotateCcw size={14} />
          </Button>
          <Button variant="ghost" size="icon" className="h-8 w-8 rounded-lg bg-white/10 border border-white/10 text-white hover:bg-white/15" onClick={() => setZoom((z) => Math.min(4, z + 0.25))} aria-label="Zoom in">
            <ZoomIn size={14} />
          </Button>
          <div className="w-px h-6 bg-white/10 mx-1" />
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 rounded-lg bg-white text-black hover:bg-white/90"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={14} />
          </Button>
        </div>
      </div>

      {/* Canvas */}
      <div
        className="flex-1 min-h-0 relative overflow-hidden grid place-items-center p-4 select-none"
        onClick={(e) => e.stopPropagation()}
        onMouseDown={(e) => {
          if (zoom <= 1) return;
          setDragging(true);
          setDragStart([e.clientX - offset[0], e.clientY - offset[1]]);
        }}
        onMouseMove={(e) => {
          if (!dragging) return;
          setOffset([e.clientX - dragStart[0], e.clientY - dragStart[1]]);
        }}
        onMouseUp={() => setDragging(false)}
        onMouseLeave={() => setDragging(false)}
        onWheel={(e) => {
          e.preventDefault();
          const delta = e.deltaY > 0 ? -0.1 : 0.1;
          setZoom((z) => Math.min(4, Math.max(0.5, z + delta)));
        }}
      >
        {!loaded && (
          <div className="absolute inset-4 grid place-items-center">
            <div className="h-[68%] w-[68%] max-w-[900px] rounded-xl border border-white/10 bg-white/[0.04] animate-pulse" />
          </div>
        )}
        <div
          className="relative max-w-[92vw] max-h-[72vh] overflow-hidden rounded-xl border border-white/10 bg-black shadow-[0_24px_80px_rgba(0,0,0,0.6)]"
          style={{
            transform: `translate(${offset[0]}px, ${offset[1]}px) scale(${zoom})`,
            cursor: dragging ? "grabbing" : zoom > 1 ? "grab" : "zoom-in",
            transition: dragging ? "none" : "transform 180ms ease",
          }}
        >
          <img
            src={image.src}
            alt={image.alt}
            className="max-w-[88vw] max-h-[72vh] object-contain block"
            draggable={false}
            onLoad={() => setLoaded(true)}
            onError={() => setLoaded(true)}
          />
          {bbox && (
            <div
              className="absolute border-2 border-[#06B6D4] bg-[#06B6D4]/15 rounded-sm shadow-[0_0_16px_rgba(6,182,212,0.5)] pointer-events-none"
              style={{
                left: `${bbox[0] * 100}%`,
                top: `${bbox[1] * 100}%`,
                width: `${(bbox[2] - bbox[0]) * 100}%`,
                height: `${(bbox[3] - bbox[1]) * 100}%`,
              }}
            >
              <div className="absolute -top-6 left-0 bg-[#06B6D4] text-white text-[11px] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap">
                {image.bboxLabel || "detection"} {image.confidence ? `${Math.round((image.confidence as number) * 100)}%` : ""}
              </div>
            </div>
          )}
        </div>
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-2 rounded-full bg-black/60 backdrop-blur border border-white/10 px-3 py-1.5 text-[11px] text-white/70">
          <span className="hidden sm:inline">Drag to pan when zoomed · Scroll to zoom · Esc to close</span>
          <span className="sm:hidden">Pinch to zoom · Tap outside to close</span>
        </div>
      </div>

      {/* Footer actions */}
      <div className="h-12 shrink-0 flex items-center justify-between px-4 border-t border-white/10 bg-black/40" onClick={(e) => e.stopPropagation()}>
        <span className="text-[11px] text-white/60">Satiq — chat viewer only · imagery stays in conversation</span>
        <div className="flex items-center gap-2">
          <button
            onClick={async () => {
              try { await navigator.clipboard.writeText(image.src); } catch {}
            }}
            className="inline-flex items-center gap-1.5 rounded-full bg-white/10 border border-white/10 px-3 py-1.5 text-xs text-white hover:bg-white/15 transition-colors"
          >
            <Copy size={12} /> Copy link
          </button>
          <a
            href={image.src}
            download={image.alt || "satiq-image"}
            className="inline-flex items-center gap-1.5 rounded-full bg-white text-black px-3 py-1.5 text-xs font-medium hover:bg-white/90 transition-colors"
          >
            <Download size={12} /> Download
          </a>
        </div>
      </div>
    </div>
  );
}
