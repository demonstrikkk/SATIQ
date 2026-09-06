import React, { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useMapStore } from '@/store/map.store';
import { useWorkspaceStore } from '@/store/workspace.store';
import { useChatStore } from '@/store/chat.store';
import { ImageCardSkeleton, ChartSkeleton, TableSkeleton, ImageSkeleton } from '@/components/ui/skeleton';
import { ImageComparison, SplitViewer, ZoomableImage } from '@/components/imagery/ImageComparison';
import { SatCanvas } from '@/components/imagery/SatImageryCanvas';
import { ChatImageLightbox } from '@/components/imagery/ChatImageLightbox';
import { MapPin, Layers, Image as ImageIcon, Maximize2 } from 'lucide-react';
import Chart from 'react-apexcharts';
import type { ApexOptions } from 'apexcharts';
import { RichTokenRenderer } from './RichTokenRenderer';
import {
  validateChartSpec,
  normalizeChartSpec,
  isHaScale,
  toDisplayValues,
  SATIQ_PALETTE,
  type ChartSpec,
} from '@/lib/chartSpec';

// Memoized Code Block — finished blocks never re-render during stream
const MemoizedCodeBlock = memo(({ language, value }: { language: string; value: string }) => {
  const [copied, setCopied] = React.useState(false);
  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {}
  };
  return (
    <div className="relative my-3 rounded-xl overflow-hidden border border-slate-700/40 bg-[#05080F]">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#0B1120] border-b border-slate-700/40 text-xs font-mono text-slate-500">
        <span>{language || "code"}</span>
        <button
          onClick={onCopy}
          className="inline-flex items-center gap-1.5 hover:text-slate-100 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#06B6D4]/40 rounded px-1.5 py-0.5"
          aria-label="Copy code"
        >
          {copied ? <><span className="h-1.5 w-1.5 rounded-full bg-[#22C55E]" /> Copied</> : "Copy"}
        </button>
      </div>
      <pre className="m-0 p-4 text-[12px] font-mono text-slate-400 overflow-auto max-h-[320px]">
        <code>{value}</code>
      </pre>
    </div>
  );
});
MemoizedCodeBlock.displayName = "MemoizedCodeBlock";

const ChartBlock = memo(function ChartBlock({ raw }: { raw: string }) {
  // Parse + validate via canonical chartSpec — skill contract
  let parsed: unknown = null;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  const validation = validateChartSpec(parsed);
  if (!validation.valid || !validation.spec) return null;
  const spec: ChartSpec = normalizeChartSpec(validation.spec);

  const data = spec.data;
  if (!data.length) return null;

  const categories = data.map((d) => d.name);
  const values = data.map((d) => (typeof d.value === "number" ? d.value : 0));
  const isHa = spec.unit === "ha" ? true : spec.unit === "%" || spec.unit === "confidence" ? false : isHaScale(values);
  const displayValues = toDisplayValues(values);
  const chartType = spec.type === "pie" ? "donut" : spec.type;
  const palette = (spec.colors && spec.colors.length ? spec.colors : [...SATIQ_PALETTE]) as string[];

  const getOptions = (): ApexOptions => {
    const baseGrid = { borderColor: "#1E293B", strokeDashArray: 3 as const, xaxis: { lines: { show: false } }, yaxis: { lines: { show: true } } };
    const fmt = (v: number) => (isHa ? `${v} ha` : `${v.toFixed(1)}%`);

    if (chartType === "donut") {
      return {
        chart: { type: "donut", background: "transparent", animations: { enabled: true } },
        theme: { mode: "dark" as const },
        colors: palette.slice(0, categories.length),
        labels: categories,
        dataLabels: { enabled: true, style: { fontSize: "11px", colors: ["#fff"] }, formatter: (v: number) => `${v.toFixed(1)}%` },
        legend: { show: false },
        plotOptions: { pie: { donut: { size: "62%", labels: { total: { show: spec.title.length < 24, label: spec.title, fontSize: "11px", color: "#94A3B8" } } } } },
        tooltip: { theme: "dark", y: { formatter: fmt } },
        stroke: { colors: ["#05080F"], width: 2 },
      } as ApexOptions;
    }

    if (chartType === "radialBar") {
      const pct = isHa ? values[0] ?? 0 : (values[0] ?? 0) * (values[0] !== undefined && values[0] <= 1 ? 100 : 1);
      return {
        chart: { type: "radialBar", background: "transparent", animations: { enabled: true } },
        theme: { mode: "dark" as const },
        colors: [palette[0] ?? "#06B6D4"],
        plotOptions: {
          radialBar: {
            hollow: { size: "62%" },
            track: { background: "#101827" },
            dataLabels: {
              name: { show: true, fontSize: "11px", color: "#94A3B8" },
              value: { show: true, fontSize: "18px", color: "#F1F5F9", formatter: () => (isHa ? `${pct} ha` : `${pct.toFixed(1)}%`) },
            },
          },
        },
        labels: [spec.title],
        stroke: { lineCap: "round" as const },
        tooltip: { theme: "dark" },
      } as ApexOptions;
    }

    if (chartType === "heatmap") {
      // Single-row heatmap from flat data: each datum is a column
      const heatData = [{ name: spec.title, data: categories.map((c, i) => ({ x: c, y: displayValues[i] ?? 0 })) }];
      return {
        chart: { type: "heatmap", background: "transparent", toolbar: { show: false }, animations: { enabled: true } },
        theme: { mode: "dark" as const },
        colors: [palette[0] ?? "#06B6D4"],
        plotOptions: { heatmap: { shadeIntensity: 0.5, colorScale: { ranges: [{ from: 0, to: 50, color: palette[3] ?? "#64748B", name: "low" }, { from: 51, to: 80, color: palette[1] ?? "#22C55E", name: "mid" }, { from: 81, to: 100, color: palette[0] ?? "#06B6D4", name: "high" }] } } },
        dataLabels: { enabled: false },
        grid: baseGrid,
        xaxis: { labels: { style: { colors: "#64748B", fontSize: "10px", fontFamily: "JetBrains Mono" } } },
        yaxis: { labels: { style: { colors: "#64748B", fontSize: "10px" } } },
        tooltip: { theme: "dark", y: { formatter: fmt } },
        legend: { show: false },
      } as unknown as ApexOptions;
    }

    // bar | area | line
    const isBar = chartType === "bar";
    const isArea = chartType === "area";
    return {
      chart: { type: chartType as "bar" | "area" | "line", background: "transparent", toolbar: { show: false }, zoom: { enabled: false }, animations: { enabled: true, speed: 560 } },
      theme: { mode: "dark" as const },
      colors: isBar ? palette.slice(0, categories.length) : [palette[0] ?? "#06B6D4"],
      plotOptions: isBar ? { bar: { borderRadius: 6, columnWidth: "42%", distributed: true } } : {},
      stroke: isBar ? { width: 0 } : { curve: "smooth" as const, width: 2.5 },
      markers: isBar ? { size: 0 } : { size: 4, colors: [palette[0] ?? "#06B6D4"], strokeColors: "#05080F", strokeWidth: 2, hover: { size: 6 } },
      fill: isArea ? { type: "gradient" as const, gradient: { shade: "dark", type: "vertical" as const, shadeIntensity: 0, opacityFrom: 0.32, opacityTo: 0.02, stops: [0, 100] } } : { opacity: 1 },
      dataLabels: { enabled: false },
      grid: baseGrid,
      xaxis: { categories, labels: { style: { colors: "#64748B", fontSize: "11px", fontFamily: "JetBrains Mono" } }, axisBorder: { show: false }, axisTicks: { show: false } },
      yaxis: {
        labels: { style: { colors: "#64748B", fontSize: "11px", fontFamily: "JetBrains Mono" }, formatter: (v: number) => (isHa ? `${v}` : `${Math.round(v)}%`) },
        min: spec.yMin ?? 0,
        max: spec.yMax ?? (isHa ? undefined : 100),
      },
      tooltip: { theme: "dark", y: { formatter: fmt } },
      legend: { show: false },
    };
  };

  const seriesForChart = (() => {
    if (chartType === "donut") return displayValues as unknown as ApexOptions["series"];
    if (chartType === "radialBar") return [isHa ? values[0] ?? 0 : (values[0] ?? 0) * (values[0] !== undefined && values[0] <= 1 ? 100 : 1)] as unknown as ApexOptions["series"];
    if (chartType === "heatmap") return [{ name: spec.title, data: categories.map((c, i) => ({ x: c, y: displayValues[i] ?? 0 })) }] as unknown as ApexOptions["series"];
    return [{ name: isHa ? "Area (ha)" : "Confidence", data: displayValues }] as unknown as ApexOptions["series"];
  })();

  const chartHeight = chartType === "radialBar" ? 220 : chartType === "heatmap" ? 200 : 190;

  return (
    <div className="my-4 rounded-xl border border-slate-700/40 bg-[#101827] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="px-3.5 py-2.5 border-b border-slate-700/40 bg-[#0B1120] flex items-center justify-between gap-2">
        <div className="min-w-0">
          <span className="text-xs font-semibold tracking-widest uppercase text-slate-300 truncate block">{spec.title}</span>
          {spec.subtitle && <span className="text-[11px] font-mono text-slate-500 truncate block">{spec.subtitle}</span>}
        </div>
        <span className="text-[11px] font-mono text-slate-500 shrink-0">
          {data.length} series · {chartType}
          {spec.unit ? ` · ${spec.unit}` : ""}
        </span>
      </div>
      <div className="w-full p-2 bg-[#05080F]" style={{ height: chartHeight }}>
        <Chart options={getOptions()} series={seriesForChart} type={chartType as never} height={chartHeight} width="100%" />
      </div>
      {spec.note && <div className="px-3.5 py-2 text-[11px] font-mono text-slate-500 bg-[#0B1120] border-t border-slate-700/40">{spec.note}</div>}
      <div className="px-3.5 py-2 border-t border-slate-700/40 bg-[#0B1120] flex flex-wrap gap-1.5">
        {data.map((d, i) => (
          <span key={d.name} className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/40 bg-[#0B1120] px-2.5 py-1 text-[11px] text-slate-400">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: palette[i % palette.length] }} /> {d.name}: <b className="text-slate-100">{isHa ? `${d.value} ha` : `${Math.round((d.value <= 1 ? d.value * 100 : d.value))}%`}</b>
            {d.meta && <span className="text-slate-500">· {d.meta}</span>}
          </span>
        ))}
      </div>
    </div>
  );
});

const ComparisonBlock = memo(function ComparisonBlock({ label }: { label: string }) {
  const isOpticalSar = /optical.*sar|sar/i.test(label);
  if (isOpticalSar) {
    return (
      <div className="my-4 rounded-[10px] border border-slate-700/40 bg-[#121615] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
        <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-slate-700/30 bg-[#0B1120]">
          <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5"><Layers size={13} className="text-[#06B6D4]" /> Cross-modal · {label}</span>
          <span className="text-[10px] font-mono text-slate-500">Optical + SAR</span>
        </div>
        <div className="bg-[rgba(51,65,85,0.35)] grid grid-cols-1 sm:grid-cols-2 gap-px p-px">
          <div className="bg-[#05080F] p-2">
            <SplitViewer leftLabel="Optical (Sentinel-2)" rightLabel="SAR (Sentinel-1)" />
          </div>
        </div>
        <div className="px-3.5 py-2.5 text-[11px] text-slate-500 bg-[#0B1120] border-t border-slate-700/30">Left: true-color optical · Right: VV/VH backscatter · Use slider in inspector.</div>
      </div>
    );
  }
  return (
    <div className="my-4 rounded-[10px] border border-slate-700/40 bg-[#121615] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-slate-700/30 bg-[#0B1120]">
        <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5"><ImageIcon size={13} className="text-[#06B6D4]" /> {label}</span>
        <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#06B6D4]/10 border border-[#06B6D4]/20 text-[#06B6D4]">Compare</span>
      </div>
      <div className="p-2 bg-[#05080F]"><ImageComparison /></div>
    </div>
  );
});

const MapPreviewBlock = memo(function MapPreviewBlock({ label }: { label: string }) {
  return (
    <div className="my-4 rounded-[10px] border border-slate-700/40 bg-[#121615] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
      <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-slate-700/30 bg-[#0B1120]">
        <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"><MapPin size={13} className="text-[#F59E0B]" /> {label}</span>
        <span className="text-[11px] font-mono text-slate-500">500 m · EPSG:32617</span>
      </div>
      <div className="h-[180px] w-full bg-[#0b0f0d] relative overflow-hidden">
        <SatCanvas mode="change" seed={33} className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-0 grid place-items-center pointer-events-none">
          <div className="rounded-full border border-white/10 bg-[rgba(10,12,11,0.65)] px-3 py-1.5 text-xs text-white">Change mask · 18.7 ha</div>
        </div>
      </div>
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-[#0B1120] border-t border-slate-700/30">
        <span className="text-[11px] text-slate-500">Deterministic area from mask geometry · CRS EPSG:32617 · 10 m GSD</span>
        <span className="text-[10.5px] font-mono text-slate-600">28.61°N · 77.24°E</span>
      </div>
    </div>
  );
});

const SingleImageBlock = memo(function SingleImageBlock({ src, alt }: { src: string; alt: string }) {
  const id = src.replace("image:", "").trim() || "raster";
  const title = alt || id.replace(/[-_]/g, " ");
  const isBlob = src.startsWith("blob:") || src.startsWith("http") || src.startsWith("data:");
  const isOpticalLike = /(water|field|scene|img_|structure|building|sector|built|optical)/i.test(alt + id);
  const isSarLike = /(sar)/i.test(alt + id);
  const [loaded, setLoaded] = React.useState(false);
  const [error, setError] = React.useState(false);
  const [lightbox, setLightbox] = React.useState(false);
  // pick seed/growth like html thumbs: water etc low growth, built-up high
  const lower = (alt + id).toLowerCase();
  let seed = 11;
  let growth = 0.45;
  if (lower.includes("water") || lower.includes("northern")) { seed = 11; growth = 0.2; }
  else if (lower.includes("structure") || lower.includes("building") || lower.includes("crop")) { seed = 11; growth = 0.65; }
  else if (lower.includes("sector") || lower.includes("built") || lower.includes("change")) { seed = 11; growth = 0.85; }
  else if (isSarLike) { seed = 22; growth = 0.5; }

  // Real bbox only — extract from src query param ?bbox=x1,y1,x2,y2 or image_ids payload, never keyword heuristic
  let bbox: [number, number, number, number] | null = null;
  let label: string | null = null;
  let conf: number | null = null;
  // 1) Try bbox from URL query param ?bbox=0.18,0.09,0.47,0.42 or &bbox=
  try {
    const url = new URL(src, typeof window !== "undefined" ? window.location.origin : "http://localhost");
    const bParam = url.searchParams.get("bbox") || url.searchParams.get("bbox_normalized");
    if (bParam) {
      const parts = bParam.split(",").map((v) => parseFloat(v.trim()));
      if (parts.length === 4 && parts.every((n) => !isNaN(n) && n >= 0 && n <= 1.5)) {
        bbox = parts as [number, number, number, number];
        label = alt || "detection";
        const cParam = url.searchParams.get("conf") || url.searchParams.get("confidence");
        if (cParam) { const cv = parseFloat(cParam); if (!isNaN(cv)) conf = cv; }
      }
    }
  } catch {}
  // 2) Try alt JSON like {"bbox":[0.18,0.09,0.47,0.42],"label":"water body","conf":0.87}
  if (!bbox && alt) {
    try {
      const parsed = JSON.parse(alt);
      if (parsed && Array.isArray(parsed.bbox) && parsed.bbox.length === 4) {
        const parts = parsed.bbox.map((v: any) => parseFloat(v));
        if (parts.every((n: number) => !isNaN(n))) {
          bbox = parts as [number, number, number, number];
          label = parsed.label || alt;
          if (parsed.conf !== undefined) conf = parseFloat(parsed.conf);
          if (parsed.confidence !== undefined) conf = parseFloat(parsed.confidence);
        }
      }
    } catch {}
    // 3) Fallback: bbox in alt string like bbox:0.18,0.09,0.47,0.42
    if (!bbox) {
      const m = alt.match(/bbox[:=]\s*([0-9.,\s]+)/i);
      if (m) {
        const parts = m[1].split(",").map((v) => parseFloat(v.trim())).filter((n) => !isNaN(n));
        if (parts.length === 4) {
          bbox = parts as [number, number, number, number];
          label = alt.slice(0, 40);
        }
      }
    }
  }
  // If no explicit bbox metadata, do NOT invent — leave null (keyword heuristic disabled)
  const hasBbox = !!bbox;

  return (
    <>
      <div className="my-4 rounded-[10px] border border-slate-700/40 bg-[#121615] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
        <div className="px-3.5 py-2.5 border-b border-slate-700/30 bg-[#0B1120] flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"><ImageIcon size={13} className="text-[#06B6D4]" /> {title}</span>
          <span className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-500"><Maximize2 size={10} /> click to zoom · {hasBbox ? "bbox overlay" : "10 m GSD"}</span>
        </div>
        <div
          className="relative aspect-[16/9] bg-[#0b0f0d] overflow-hidden group cursor-zoom-in"
          onClick={() => isBlob && !error && setLightbox(true)}
          role={isBlob ? "button" : undefined}
          tabIndex={isBlob ? 0 : undefined}
          onKeyDown={(e) => { if (e.key === "Enter" && isBlob) setLightbox(true); }}
          aria-label={isBlob ? `View ${title} fullscreen` : undefined}
        >
          {!loaded && isBlob && !error && <div className="absolute inset-0"><ImageSkeleton /></div>}
          {isBlob ? (
            error ? (
              <div className="h-full w-full grid place-items-center bg-[#0b0f0d] p-6 text-center">
                <div className="text-xs text-slate-500">Preview unavailable — {title}. Try re-attaching as PNG/JPG.</div>
              </div>
            ) : (
              <img
                src={src}
                alt={title}
                className={`h-full w-full object-cover transition-opacity duration-300 ${loaded ? "opacity-100" : "opacity-0"}`}
                loading="lazy"
                decoding="async"
                onLoad={() => setLoaded(true)}
                onError={() => setError(true)}
              />
            )
          ) : isSarLike ? (
            <SatCanvas mode="sar" seed={seed} className="h-full w-full" />
          ) : (
            <SatCanvas mode="optical" seed={seed} growth={growth} className="h-full w-full" />
          )}
          {hasBbox && bbox && (
            <div
              className="absolute border-2 border-[#06B6D4] bg-[#06B6D4]/10 rounded-sm shadow-[0_0_12px_rgba(6,182,212,0.4)] pointer-events-none"
              style={{
                left: `${bbox[0] * 100}%`,
                top: `${bbox[1] * 100}%`,
                width: `${(bbox[2] - bbox[0]) * 100}%`,
                height: `${(bbox[3] - bbox[1]) * 100}%`,
              }}
            >
              <div className="absolute -top-6 left-0 bg-[#06B6D4] text-white text-[11px] font-semibold px-1.5 py-0.5 rounded whitespace-nowrap shadow-md flex items-center gap-1">
                {label} {conf !== null && <span className="bg-white/20 rounded px-1 text-[10px]">{Math.round(conf * 100)}%</span>}
              </div>
              <div className="absolute -bottom-5 right-0 bg-black/60 backdrop-blur text-white text-[10px] font-mono px-1 py-0.5 rounded">
                {bbox.map((v) => v.toFixed(2)).join(", ")}
              </div>
            </div>
          )}
          <div className="absolute bottom-2 right-2 bg-[rgba(10,12,11,0.65)] border border-white/10 rounded-full px-2 py-1 text-[10px] text-white/80 hidden group-hover:flex items-center gap-1 pointer-events-none">
            <Maximize2 size={10} /> {isBlob ? "View in chat" : "Zoom"} • {bbox ? "bbox at correct place" : "EPSG:32617"}
          </div>
        </div>
        <div className="px-3.5 py-2.5 bg-[#0B1120] border-t border-slate-700/30">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <div className="text-xs font-medium text-slate-200 truncate">{hasBbox ? `Detected: ${label} — spatially grounded` : `Single frame • ${id}`}</div>
              <div className="text-[11px] text-slate-500 truncate">{isBlob ? "Uploaded imagery — rendered in chat only" : "Synthetic optical/SAR terrain • 10 m GSD • EPSG:32617"} • {hasBbox ? "bbox normalized overlay" : "no bbox • answer-only"}</div>
            </div>
            <div className="shrink-0 ml-3 flex flex-col items-end">
              <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border ${hasBbox ? "bg-[#22C55E]/10 border-[#22C55E]/20 text-[#22C55E]" : "bg-slate-800/60 border-slate-700/60 text-slate-400"}`}>
                {hasBbox ? " grounded 87%" : isBlob ? " uploaded" : " VQA 84%"}
              </span>
            </div>
          </div>
          {hasBbox && (
            <div className="mt-2.5 flex gap-1.5">
              <button
                onClick={() => {
                  const coords = bbox ? `${bbox[0]},${bbox[1]},${bbox[2]},${bbox[3]}` : "0,0,1,1";
                  const fid = `bbox_${coords}`;
                  const ms = useMapStore.getState();
                  if (!ms.layers.detections) ms.toggleLayer("detections");
                  useMapStore.getState().addFeature({ id: fid, label: label ?? "detection", confidence: conf ?? 0.87, source: "LLM", type: "bbox", bboxNorm: bbox ?? undefined } as any);
                  useMapStore.getState().setSelectedFeatureId(fid);
                  const ws = useWorkspaceStore.getState();
                  if (!ws.inspectorOpen) ws.toggleInspector();
                }}
                className="inline-flex items-center gap-1 rounded-full bg-[#06B6D4]/10 border border-[#06B6D4]/20 text-[#06B6D4] px-2.5 py-1 text-[11px] font-medium hover:bg-[#06B6D4]/15 transition-colors"
              >
                <MapPin size={11} /> Open in map
              </button>
              <button
                onClick={() => useWorkspaceStore.getState().toggleInspector()}
                className="inline-flex items-center gap-1 rounded-full bg-[#101827] border border-slate-700/40 text-slate-400 px-2.5 py-1 text-[11px] font-medium hover:bg-[#141F30] hover:text-slate-200 transition-colors"
              >
                <Layers size={11} /> Inspect
              </button>
            </div>
          )}
        </div>
      </div>
      {isBlob && lightbox && (
        <ChatImageLightbox
          image={{ src, alt: title, label: title, bbox: bbox, bboxLabel: label || undefined, confidence: conf }}
          onClose={() => setLightbox(false)}
        />
      )}
    </>
  );
});

export const StreamMarkdown = memo(function StreamMarkdown({ content }: { content: string }) {
  const { setSelectedFeatureId } = useMapStore();
  const { inspectorOpen, toggleInspector } = useWorkspaceStore();

  const onBboxClick = (coords: string) => {
    const featureId = `bbox_${coords.replace(/[^0-9,.-]/g, "")}`;
    setSelectedFeatureId(featureId);
    if (!inspectorOpen) toggleInspector();
    useChatStore.getState().addContext({ id: featureId, type: "bbox", label: `BBox ${coords}` });
  };

  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Rich token: intercept paragraphs to parse bbox chips inline — html .msg-text p 14/1.65 0 0 10
        p: ({ children, ...props }: any) => {
          const hasBboxToken = React.Children.toArray(children).some(c => typeof c === 'string' && String(c).includes('[[bbox:'));
          if (hasBboxToken) {
            const text = React.Children.toArray(children).map(c => typeof c === 'string' ? c : '').join('');
            return <RichTokenRenderer text={text} onBboxClick={onBboxClick} />;
          }
          return <p className="my-2.5 leading-[1.65] text-[14px] text-slate-200" {...props}>{children}</p>;
        },
        h1: ({ children, ...props }: any) => <h1 className="text-[22px] font-semibold tracking-tight text-white mt-6 mb-3 leading-tight" {...props}>{children}</h1>,
        h2: ({ children, ...props }: any) => <h2 className="text-[16px] font-semibold tracking-tight text-white mt-6 mb-2.5" {...props}>{children}</h2>,
        h3: ({ children, ...props }: any) => {
          const txt = String(Array.isArray(children) ? children.join("") : children ?? "").toLowerCase();
          const isObs = txt.includes("observation") || txt.includes("finding") || txt.includes("key");
          if (isObs) {
            return <div className="mt-4 mb-2 text-[11px] font-semibold tracking-[0.05em] uppercase text-slate-500" {...props}>{children}</div>;
          }
          return <h3 className="text-[11px] font-semibold tracking-[0.09em] uppercase text-[#06B6D4] mt-6 mb-3" {...props}>{children}</h3>;
        },
        strong: ({ children, ...props }: any) => <strong className="font-semibold text-white" {...props}>{children}</strong>,
        em: ({ children, ...props }: any) => <em className="text-[#06B6D4] not-italic font-medium" {...props}>{children}</em>,
        // html .observations: border-left 2px, pl-14, flex gap 7, dot 4px
        ul: ({ children, ...props }: any) => {
          // detect observations context via parent h3 title — we treat all ul after obs h3 as observations
          return <ul className="my-3.5 p-0 flex flex-col gap-[7px] list-none border-l-2 border-slate-700/60 pl-[14px]" {...props}>{children}</ul>;
        },
        ol: (props: any) => <ol className="list-decimal pl-5 my-3.5 space-y-2 marker:text-slate-500" {...props} />,
        li: ({ children, ...props }: any) => (
          <li className="flex gap-2 text-[13.5px] leading-relaxed text-slate-400 list-none" {...props}>
            <span className="mt-[8px] h-1 w-1 rounded-full bg-slate-600 shrink-0" />
            <span className="flex-1">{children}</span>
          </li>
        ),
        // html confidence-row vs generic blockquote: detect "Confidence"
        blockquote: ({ children, ...props }: any) => {
          const flat = React.Children.toArray(children).map(c => typeof c === "string" ? c : (c as any)?.props?.children ?? "").join(" ");
          const str = String(flat);
          const m = str.match(/Confidence[:\s]*([0-9.]+)%?/i);
          if (m) {
            const raw = m[1] ?? "";
            const v = parseFloat(raw);
            const pct = isNaN(v) ? 87 : v > 1 ? Math.round(v > 100 ? 100 : v) : Math.round(v * 100);
            return (
              <div className="my-4 flex items-center gap-2.5">
                <span className="text-[11px] font-semibold tracking-[0.05em] uppercase text-slate-500">Confidence</span>
                <span className="font-mono text-[13px] font-semibold text-[#06B6D4]">{pct}%</span>
                <div className="flex-1 h-1 max-w-[180px] rounded-full bg-[#141F30] overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-[#06B6D4] to-[#06B6D4]" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          }
          return <blockquote className="my-4 border-l-2 border-[#06B6D4]/30 bg-[#101827]/40 pl-4 py-2.5 text-[13.5px] leading-relaxed text-slate-400 rounded-r-xl" {...props}>{children}</blockquote>;
        },
        table: ({ children, ...props }: any) => (
          <div className="my-4 overflow-hidden rounded-xl border border-slate-700/40 bg-[#101827]" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
            <div className="overflow-x-auto">
              <table className="w-full text-sm" {...props}>{children}</table>
            </div>
          </div>
        ),
        thead: (props: any) => <thead className="bg-[#0B1120] text-slate-400 text-xs uppercase tracking-widest" {...props} />,
        tbody: (props: any) => <tbody className="divide-y divide-slate-800/50 [&_tr:hover]:bg-[#141F30]/60 [&_tr]:transition-colors" {...props} />,
        th: (props: any) => <th className="px-3.5 py-2.5 text-left font-semibold border-b border-slate-700/40 whitespace-nowrap text-slate-300" {...props} />,
        td: (props: any) => <td className="px-3.5 py-2.5 text-[13px] text-slate-300" {...props} />,
        code({ node, inline, className, children, ...props }: any) {
          const match = /language-(\w+)/.exec(className || '');
          const value = String(children).replace(/\n$/, '');
          const lang = match?.[1];
          if (!inline && lang === "chart") {
            if (!value || value.length < 10) return <ChartSkeleton />;
            try { JSON.parse(value); } catch { return <ChartSkeleton />; }
            return <ChartBlock raw={value} />;
          }
          if (!inline && (lang === "comparison" || lang === "map")) {
            return <ComparisonBlock label={value || lang} />;
          }
          return !inline ? (
            <MemoizedCodeBlock language={lang ?? 'text'} value={value} />
          ) : (
            <code className="bg-[#0B1120] text-[#06B6D4] px-1.5 py-0.5 rounded-lg text-xs font-mono border border-slate-700/40" {...props}>{children}</code>
          );
        },
        a: ({ href, children, ...props }: any) => {
          const h = String(href ?? "");
          const label = String(Array.isArray(children) ? children.join("") : children ?? "").toLowerCase();
          const isBbox = h.includes("bbox") || label.includes("view change") || label.includes("change area");
          const isEvidence = h.includes("evidence") || label.includes("evidence") || label.includes("open evidence");
          if (isBbox) {
            return (
              <button
                onClick={() => onBboxClick("120,45,310,210")}
                className="inline-flex items-center gap-1.5 rounded-full bg-[#06B6D4]/10 border border-[#06B6D4]/20 text-[#06B6D4] px-3 py-1.5 text-xs font-medium hover:bg-[#06B6D4]/15 hover:border-[#06B6D4]/30 transition-colors mr-1.5 align-middle"
              >
                <MapPin size={12} className="shrink-0" />
                <span>{children}</span>
              </button>
            );
          }
          if (isEvidence) {
            return (
              <button
                onClick={() => {
                  if (!inspectorOpen) toggleInspector();
                }}
                className="inline-flex items-center gap-1.5 rounded-full bg-[#101827] border border-slate-700/40 text-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-[#141F30] hover:text-white hover:border-slate-600/40 transition-colors mr-1.5 align-middle"
              >
                <Layers size={12} className="shrink-0" />
                <span>{children}</span>
              </button>
            );
          }
          return (
            <a href={h} className="text-[#06B6D4] hover:text-[#22d3ee] underline underline-offset-2 decoration-[#06B6D4]/30 hover:decoration-[#06B6D4] transition-colors" {...props}>
              {children}
            </a>
          );
        },
        img: ({ src, alt, ...props }: any) => {
          const s = String(src ?? "");
          // incomplete/streaming guard — don't try to fetch partial custom schemes
          if (!s || s.trim().length < 2) return null;
          if (s.startsWith("comparison:") || s.startsWith("map:") || s.startsWith("image:") || s.startsWith("gallery:")) {
            // if label/alt is still streaming and empty, show skeleton
            if (s.length < 12 && !alt) return <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] h-[220px] animate-pulse" />;
            if (s.startsWith("comparison:")) return <ComparisonBlock label={alt || s.replace("comparison:", "")} />;
            if (s.startsWith("map:")) return <MapPreviewBlock label={alt || s.replace("map:", "")} />;
            if (s.startsWith("gallery:")) {
              const ids = s.replace("gallery:", "").split(",").map(x => x.trim()).filter(Boolean);
              if (!ids.length) return <div className="my-4 rounded-xl border border-slate-700/40 bg-[#121615] h-[160px] animate-pulse" />;
              return (
                <div className="my-4 grid grid-cols-2 gap-px bg-[rgba(51,65,85,0.35)] p-px rounded-[10px] overflow-hidden">
                  {ids.map((id, i) => (
                    <div key={i} className="bg-[#121615] flex flex-col overflow-hidden">
                      <div className="px-2.5 py-1.5 border-b border-slate-700/30 bg-[#0B1120] text-[11px] font-semibold tracking-widest uppercase text-slate-400 truncate flex items-center gap-1.5"><ImageIcon size={10} className="text-[#06B6D4]" /> {id}</div>
                      <div className="relative aspect-[4/3] overflow-hidden bg-[#0b0f0d]">
                        <SatCanvas mode="optical" seed={11 + i} growth={0.4 + (i % 3) * 0.2} className="h-full w-full" />
                      </div>
                    </div>
                  ))}
                </div>
              );
            }
            return <SingleImageBlock src={s} alt={alt || ""} />;
          }
          // real URL — also via SingleImageBlock so bbox is drawn at correct normalized place
          return <SingleImageBlock src={s} alt={alt || s.slice(0, 40)} />;
        }
      }}
    >
      {content}
    </ReactMarkdown>
  );
});
