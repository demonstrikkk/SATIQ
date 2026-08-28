import React, { memo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useMapStore } from '@/store/map.store';
import { useWorkspaceStore } from '@/store/workspace.store';
import { useChatStore } from '@/store/chat.store';
import { ImageCardSkeleton, ChartSkeleton, TableSkeleton } from '@/components/ui/skeleton';
import { ImageComparison, SplitViewer, ZoomableImage } from '@/components/imagery/ImageComparison';
import { MapPin, Layers, Image as ImageIcon, Maximize2 } from 'lucide-react';
import Chart from 'react-apexcharts';
import type { ApexOptions } from 'apexcharts';
import { RichTokenRenderer } from './RichTokenRenderer';

// Memoized Code Block — finished blocks never re-render during stream
const MemoizedCodeBlock = memo(({ language, value }: { language: string; value: string }) => (
  <div className="relative my-3 rounded-lg overflow-hidden border border-slate-800/60 bg-[#090D14]">
    <div className="flex items-center justify-between px-3 py-1.5 bg-[#0D121F] border-b border-slate-800/60 text-xs font-mono text-[#64748B]">
      <span>{language || 'code'}</span>
      <button
        onClick={() => navigator.clipboard.writeText(value)}
        className="hover:text-[#F8FAFC] transition-colors"
      >
        Copy
      </button>
    </div>
    <pre className="m-0 p-4 text-[12px] font-mono text-[#94A3B8] overflow-auto max-h-[320px]">
      <code>{value}</code>
    </pre>
  </div>
));
MemoizedCodeBlock.displayName = 'MemoizedCodeBlock';

const ChartBlock = memo(function ChartBlock({ raw }: { raw: string }) {
  let parsed: any = null;
  try { parsed = JSON.parse(raw); } catch { return null; }
  const data: { name: string; value: number }[] = parsed?.data ?? [];
  const title: string = parsed?.title ?? "Analysis";
  const type: string = parsed?.type ?? "bar";
  const colors = ["#06B6D4", "#22C55E", "#F59E0B", "#64748B", "#38bdf8"];
  if (!data.length) return null;

  const categories = data.map(d => d.name);
  const values = data.map(d => (typeof d.value === "number" ? d.value : 0));
  const isHa = values.some(v => v > 2);
  const displayValues = isHa ? values : values.map(v => Number((v * 100).toFixed(1)));
  const chartType = type === "donut" || type === "pie" ? "donut" : (type as any);
  const isDonut = chartType === "donut";

  const getOptions = (): ApexOptions => {
    if (isDonut) {
      return {
        chart: { type: "donut", background: "transparent", animations: { enabled: true } },
        theme: { mode: "dark" as const },
        colors,
        labels: categories,
        dataLabels: { enabled: true, style: { fontSize: "11px", colors: ["#fff"] } },
        legend: { show: false },
        plotOptions: { pie: { donut: { size: "62%" } } },
        tooltip: { theme: "dark", y: { formatter: (v: number) => (isHa ? `${v} ha` : `${v.toFixed(1)}%`) } },
        stroke: { colors: ["#090D14"], width: 2 },
      } as ApexOptions;
    }
    return {
      chart: { type: chartType as any, background: "transparent", toolbar: { show: false }, zoom: { enabled: false }, animations: { enabled: true, speed: 560 } },
      theme: { mode: "dark" as const },
      colors: chartType === "bar" ? colors : ["#06B6D4"],
      plotOptions: chartType === "bar" ? { bar: { borderRadius: 6, columnWidth: "42%" } } : {},
      stroke: chartType === "bar" ? { width: 0 } : { curve: "smooth" as const, width: 2.5 },
      markers: chartType === "bar" ? { size: 0 } : { size: 4, colors: ["#06B6D4"], strokeColors: "#090D14", strokeWidth: 2, hover: { size: 6 } },
      fill: chartType === "area" ? { type: "gradient" as const, gradient: { shade: "dark", type: "vertical" as const, shadeIntensity: 0, opacityFrom: 0.32, opacityTo: 0.02, stops: [0, 100] } } : { opacity: 1 },
      dataLabels: { enabled: false },
      grid: { borderColor: "#1E293B", strokeDashArray: 3, xaxis: { lines: { show: false } }, yaxis: { lines: { show: true } } },
      xaxis: { categories, labels: { style: { colors: "#64748B", fontSize: "11px", fontFamily: "JetBrains Mono" } }, axisBorder: { show: false }, axisTicks: { show: false } },
      yaxis: { labels: { style: { colors: "#64748B", fontSize: "11px", fontFamily: "JetBrains Mono" }, formatter: (v: number) => (isHa ? `${v}` : `${Math.round(v)}%`) }, min: 0, max: isHa ? undefined : 100 },
      tooltip: { theme: "dark", y: { formatter: (v: number) => (isHa ? `${v} ha` : `${v.toFixed(1)}%`) } },
      legend: { show: false },
    };
  };

  return (
    <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] overflow-hidden">
      <div className="px-3.5 py-2.5 border-b border-slate-800/60 bg-[#0D121F] flex items-center justify-between">
        <span className="text-xs font-semibold tracking-widest uppercase text-[#94A3B8]">{title}</span>
        <span className="text-[11px] font-mono text-[#64748B]">{data.length} series · {type}</span>
      </div>
      <div className="h-[190px] w-full p-2 bg-[#090D14]">
        <Chart options={getOptions()} series={isDonut ? (values as any) : ([{ name: isHa ? "Area (ha)" : "Confidence", data: displayValues }] as any)} type={chartType as any} height={190} width="100%" />
      </div>
      <div className="px-3.5 py-2 border-t border-slate-800/60 bg-[#0D121F] flex flex-wrap gap-1.5">
        {data.map((d, i) => (
          <span key={d.name} className="inline-flex items-center gap-1.5 rounded-full border border-slate-800/60 bg-[#0D121F] px-2.5 py-1 text-[11px] text-[#94A3B8]">
            <span className="h-1.5 w-1.5 rounded-full" style={{ background: colors[i % colors.length] }} /> {d.name}: <b className="text-white">{typeof d.value === "number" && d.value > 2 ? `${d.value} ha` : `${Math.round(d.value * 100)}%`}</b>
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
    <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] overflow-hidden">
        <div className="px-3.5 py-2.5 border-b border-slate-800/60 bg-[#0D121F] text-xs font-semibold tracking-widest uppercase text-[#94A3B8] flex items-center gap-1.5"><Layers size={12} /> {label}</div>
        <div className="p-3"><SplitViewer leftLabel="Optical (Sentinel-2)" rightLabel="SAR (Sentinel-1)" /></div>
        <div className="px-3.5 pb-3 text-[11px] text-[#64748B]">Left: true-color optical • Right: VV/VH backscatter • Use slider in inspector.</div>
      </div>
    );
  }
  return (
    <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] overflow-hidden">
      <div className="px-3.5 py-2.5 border-b border-slate-800/60 bg-[#0D121F] text-xs font-semibold tracking-widest uppercase text-[#94A3B8] flex items-center gap-1.5"><ImageIcon size={12} /> {label}</div>
      <div className="p-3"><ImageComparison /></div>
      </div>
  );
});

const MapPreviewBlock = memo(function MapPreviewBlock({ label }: { label: string }) {
  return (
    <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] overflow-hidden">
      <div className="px-3.5 py-2.5 border-b border-slate-800/60 flex items-center gap-1.5 text-xs font-semibold tracking-widest uppercase text-[#F59E0B]"><MapPin size={12} /> {label}</div>
      <div className="h-[180px] w-full bg-[#090D14] relative overflow-hidden">
        <div className="absolute inset-0 opacity-20" style={{ backgroundImage: "radial-gradient(circle at 30% 30%, #06B6D4 1px, transparent 1px), radial-gradient(circle at 70% 60%, #F59E0B 1px, transparent 1px)", backgroundSize: "28px 28px" }} />
        <div className="absolute inset-0 grid place-items-center">
          <div className="rounded-xl border border-slate-800/60 bg-[#0D121F] px-3 py-2 text-xs text-white flex items-center gap-2">Change mask • 18.7 ha</div>
        </div>
      </div>
      <div className="px-3.5 py-2 text-[11px] text-[#64748B]">Deterministic area from mask geometry • CRS EPSG:32617 • 10 m GSD      </div>
    </div>
  );
});

const SingleImageBlock = memo(function SingleImageBlock({ src, alt }: { src: string; alt: string }) {
  const id = src.replace("image:", "").trim() || "raster";
  const title = alt || id.replace(/[-_]/g, " ");
  const isBlob = src.startsWith("blob:") || src.startsWith("http") || src.startsWith("data:");
  const displaySrc = isBlob
    ? src
    : `data:image/svg+xml;utf8,${encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450"><rect width="100%" height="100%" fill="#0D121F"/><rect x="0" y="0" width="800" height="450" fill="none" stroke="#1e293b" stroke-width="1"/><g opacity="0.08"><path d="M0 80 H800 M0 160 H800 M0 240 H800 M0 320 H800 M0 400 H800 M80 0 V450 M160 0 V450 M240 0 V450 M320 0 V450 M400 0 V450 M480 0 V450 M560 0 V450 M640 0 V450 M720 0 V450" stroke="#334155" stroke-width="0.5"/></g><circle cx="400" cy="225" r="70" fill="none" stroke="#06B6D4" stroke-opacity="0.15" stroke-width="1.5"/><circle cx="400" cy="225" r="110" fill="none" stroke="#F59E0B" stroke-opacity="0.08" stroke-width="1"/><text x="50%" y="46%" dominant-baseline="middle" text-anchor="middle" fill="#94A3B8" font-family="Inter,sans-serif" font-size="13" font-weight="600">${title}</text><text x="50%" y="53%" dominant-baseline="middle" text-anchor="middle" fill="#475569" font-family="JetBrains Mono,monospace" font-size="10">${id} • 5120×5120 • 10 m • Sentinel-2</text></svg>`
      )}`;

  // Try to find a bbox for this image from session/map store — show at correct normalized place
  // For demo, map known ids to known bboxes; otherwise use latest bbox if alt suggests grounding
  let bbox: [number, number, number, number] | null = null;
  let label: string | null = null;
  let conf: number | null = null;
  const lower = (alt + id).toLowerCase();
  if (lower.includes("water") || lower.includes("water-body") || lower.includes("northern aoi")) {
    bbox = [0.18, 0.09, 0.47, 0.42];
    label = "water body";
    conf = 0.87;
  } else if (lower.includes("structure") || lower.includes("building") || lower.includes("crop")) {
    bbox = [0.21, 0.11, 0.26, 0.14];
    label = "building footprint";
    conf = 0.89;
  } else if (lower.includes("sector") || lower.includes("built-up") || lower.includes("change")) {
    bbox = [0.62, 0.32, 0.84, 0.58];
    label = "built-up expansion";
    conf = 0.91;
  }

  const hasBbox = !!bbox;

  return (
    <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] overflow-hidden shadow-sm">
      <div className="px-3.5 py-2.5 border-b border-slate-800/60 bg-[#0D121F] flex items-center justify-between">
        <span className="text-xs font-semibold tracking-widest uppercase text-[#94A3B8] flex items-center gap-1.5"><ImageIcon size={12} /> {title}</span>
        <span className="inline-flex items-center gap-1 text-[11px] font-mono text-slate-500"><Maximize2 size={10} /> click to zoom • {hasBbox ? "bbox overlay" : "10 m GSD"}</span>
      </div>
      <div className="relative aspect-[16/9] bg-[#090D14] overflow-hidden group">
        <img src={displaySrc} alt={title} className="h-full w-full object-cover" loading="lazy" />
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
        <div className="absolute bottom-2 right-2 bg-black/60 backdrop-blur border border-white/10 rounded-full px-2 py-1 text-[10px] text-white/80 hidden group-hover:flex items-center gap-1">
          <Maximize2 size={10} /> Zoom • {bbox ? "bbox at correct place" : "EPSG:32617"}
        </div>
      </div>
      <div className="px-3.5 py-2.5 flex items-center justify-between bg-[#090D14]/50 border-t border-slate-800/60">
        <div className="min-w-0">
          <div className="text-xs font-medium text-slate-200 truncate">{hasBbox ? `Detected: ${label} — spatially grounded` : `Single frame • ${id}`}</div>
          <div className="text-[11px] text-slate-500 truncate">Sentinel-2 • 5120×5120 • 10 m GSD • EPSG:32617 • {hasBbox ? "bbox normalized overlay" : "no bbox • answer-only"}</div>
        </div>
        <div className="shrink-0 ml-3 flex flex-col items-end">
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium border ${hasBbox ? "bg-[#22C55E]/10 border-[#22C55E]/20 text-[#22C55E]" : "bg-slate-800/60 border-slate-700/60 text-slate-400"}`}>
            {hasBbox ? " grounded 87%" : " VQA 84%"}
          </span>
        </div>
      </div>
    </div>
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
        // Rich token: intercept paragraphs to parse bbox chips inline
        p: ({ children, ...props }: any) => {
          // Flatten children to string for RichToken check, but we want to preserve other elements
          // Use RichTokenRenderer only if text contains [[bbox:
          const hasBboxToken = React.Children.toArray(children).some(c => typeof c === 'string' && String(c).includes('[[bbox:'));
          if (hasBboxToken) {
            const text = React.Children.toArray(children).map(c => typeof c === 'string' ? c : '').join('');
            return <RichTokenRenderer text={text} onBboxClick={onBboxClick} />;
          }
          return <p className="my-2.5 leading-relaxed text-[14px] text-[#F8FAFC]" {...props}>{children}</p>;
        },
        h1: ({ children, ...props }: any) => <h1 className="text-xl font-semibold tracking-tight text-white mt-5 mb-3" {...props}>{children}</h1>,
        h2: ({ children, ...props }: any) => <h2 className="text-base font-semibold tracking-tight text-white mt-5 mb-2.5" {...props}>{children}</h2>,
        h3: ({ children, ...props }: any) => <h3 className="text-xs font-semibold tracking-[0.06em] uppercase text-[#60A5FA] mt-5 mb-3" {...props}>{children}</h3>,
        strong: ({ children, ...props }: any) => <strong className="font-semibold text-white" {...props}>{children}</strong>,
        em: ({ children, ...props }: any) => <em className="text-[#60A5FA] not-italic" {...props}>{children}</em>,
        ul: (props: any) => <ul className="list-disc pl-5 my-3 space-y-1.5 marker:text-[#64748B]" {...props} />,
        ol: (props: any) => <ol className="list-decimal pl-5 my-3 space-y-1.5 marker:text-[#64748B]" {...props} />,
        li: (props: any) => <li className="leading-relaxed text-[14px] text-[#94A3B8]" {...props} />,
        blockquote: ({ children, ...props }: any) => <blockquote className="my-3 border-l-2 border-[#06B6D4]/40 bg-[#0D121F]/50 pl-3 py-2 text-sm text-[#94A3B8] rounded-r-lg" {...props}>{children}</blockquote>,
        table: ({ children, ...props }: any) => (
          <div className="my-4 overflow-hidden rounded-xl border border-slate-800/60 bg-[#0D121F]">
            <div className="overflow-x-auto">
              <table className="w-full text-sm" {...props}>{children}</table>
            </div>
          </div>
        ),
        thead: (props: any) => <thead className="bg-[#0D121F] text-[#94A3B8] text-xs uppercase tracking-widest" {...props} />,
        tbody: (props: any) => <tbody className="divide-y divide-[#1E293B]" {...props} />,
        th: (props: any) => <th className="px-3.5 py-2.5 text-left font-semibold border-b border-slate-800/60 whitespace-nowrap" {...props} />,
        td: (props: any) => <td className="px-3.5 py-2.5 text-[13px] text-[#94A3B8]" {...props} />,
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
            <code className="bg-[#0D121F] text-[#06B6D4] px-1.5 py-0.5 rounded text-xs font-mono border border-slate-800/60" {...props}>{children}</code>
          );
        },
        a: ({ href, children, ...props }: any) => {
          const h = String(href ?? "");
          const label = String(Array.isArray(children) ? children.join("") : children ?? "").toLowerCase();
          const isBbox = h.includes("bbox") || h.includes("mock") || label.includes("view change") || label.includes("change area");
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
                className="inline-flex items-center gap-1.5 rounded-full bg-slate-800/60 border border-slate-700/60 text-slate-300 px-3 py-1.5 text-xs font-medium hover:bg-slate-700/60 hover:text-white transition-colors mr-1.5 align-middle"
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
              if (!ids.length) return <div className="my-4 rounded-xl border border-slate-800/60 bg-[#0D121F] h-[160px] animate-pulse" />;
              return (
                <div className="my-4 grid grid-cols-2 gap-2">
                  {ids.map((id, i) => {
                    const gSvg = `data:image/svg+xml;utf8,${encodeURIComponent(`<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="100%" height="100%" fill="#0D121F"/><g opacity="0.06"><path d="M0 60 H400 M0 120 H400 M0 180 H400 M0 240 H400 M60 0 V300 M120 0 V300 M180 0 V300 M240 0 V300 M300 0 V300 M360 0 V300" stroke="#334155" stroke-width="0.5"/></g><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#64748B" font-family="Inter,sans-serif" font-size="11" font-weight="600">${id}</text><text x="50%" y="58%" dominant-baseline="middle" text-anchor="middle" fill="#475569" font-family="JetBrains Mono,monospace" font-size="9">400×300 • 10 m</text></svg>`)}`;
                    return (
                      <div key={i} className="rounded-xl overflow-hidden border border-slate-800/60 bg-[#0D121F] flex flex-col">
                        <div className="px-2.5 py-1.5 border-b border-slate-800/60 bg-[#0D121F] text-[11px] font-semibold tracking-widest uppercase text-slate-400 truncate flex items-center gap-1.5"><ImageIcon size={10} /> {id}</div>
                        <div className="relative aspect-[4/3] overflow-hidden bg-[#090D14]">
                          <img src={gSvg} alt={id} className="h-full w-full object-cover" loading="lazy" />
                        </div>
                      </div>
                    );
                  })}
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
