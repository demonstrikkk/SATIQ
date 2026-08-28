import { useEffect, useState } from "react";
import { X, Clock3, Check, Loader2, CircleDot, Download, ImageIcon, BarChart3 } from "lucide-react";
import { useExecutionStore } from "@/store/execution.store";
import { useChatStore } from "@/store/chat.store";
import { Button } from "@/components/ui/button";
import { useMapStore } from "@/store/map.store";
import { ImageCardSkeleton } from "@/components/ui/skeleton";

function fmt(ts?: number) {
  if (!ts) return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function RightThinkingPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { globalStatus, pipelineSteps, plannerDetails } = useExecutionStore();
  const { messages } = useChatStore();
  const { selectedFeatureId, features } = useMapStore();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const selected = features.find(f => f.id === selectedFeatureId);
  const isInspection = !!selected;
  const artifacts = messages.filter(m => m.role === "assistant" && (m.content.includes("```") || m.content.includes("|") || m.content.includes("comparison:") || m.content.includes("map:") || m.content.includes("image:")));

  const [previewLoaded, setPreviewLoaded] = useState(false);
  useEffect(() => { setPreviewLoaded(false); }, [selectedFeatureId]);

  // Planner-driven timeline — tasks come from LLM planner, not precomputed
  const plannerTasks = (() => {
    if (!plannerDetails?.task_router_map || Object.keys(plannerDetails.task_router_map).length === 0) {
      if (globalStatus === "idle") return [] as { id: string; title: string; subtitle: string; status: string; durationMs?: number }[];
      // fallback while planner hasn't emitted yet: show pipeline as timeline so user sees progress
      return pipelineSteps.map((s) => ({ id: s.id, title: s.title, subtitle: s.subtitle ?? "", status: s.status, durationMs: s.durationMs }));
    }
    const getStatus = (key: string) => {
      const k = key.toLowerCase();
      if (k.includes("crop") || k.includes("gis") || k.includes("raster")) {
        return pipelineSteps.find((p) => p.id === "preparing")?.status ?? (globalStatus === "completed" ? "completed" : globalStatus === "idle" ? "pending" : "running");
      }
      if (k.includes("ground") || k.includes("change") || k.includes("fusion") || k.includes("vqa") || k.includes("optical") || k.includes("sar")) {
        return pipelineSteps.find((p) => p.id === "analyzing")?.status ?? pipelineSteps.find((p) => p.id === "locating")?.status ?? "pending";
      }
      if (k.includes("evidence") || k.includes("validat")) return pipelineSteps.find((p) => p.id === "validating")?.status ?? "pending";
      if (k.includes("composer") || k.includes("generat")) return pipelineSteps.find((p) => p.id === "generating")?.status ?? "pending";
      return pipelineSteps.find((p) => p.id === "understanding")?.status ?? "pending";
    };
    return Object.entries(plannerDetails.task_router_map).map(([task, model]) => ({
      id: task,
      title: task.replace(/_/g, " "),
      subtitle: String(model),
      status: getStatus(task) as string,
      durationMs: undefined as number | undefined,
    }));
  })();
  const totalMs = pipelineSteps.reduce((a, b) => a + (b.durationMs || 0), 0);
  const allCompleted = plannerTasks.length > 0 && plannerTasks.every((t) => t.status === "completed") && globalStatus === "completed";

  if (!open) return null;

  return (
    <div className="w-[360px] h-full bg-[#0D121F] flex flex-col overflow-hidden">
      <div className="h-12 shrink-0 sticky top-0 z-10 flex items-center justify-between px-4 border-b border-slate-800/60 bg-[#0D121F]">
        <span className="text-[14px] font-semibold tracking-wide text-white">{isInspection ? "INSPECTION" : "PIPELINE"}</span>
        <div className="flex items-center gap-2">
          <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium border ${globalStatus === "completed" ? "bg-[#22C55E]/10 border-[#22C55E]/20 text-[#22C55E]" : globalStatus === "failed" ? "bg-[#EF4444]/10 border-[#EF4444]/20 text-[#EF4444]" : globalStatus === "idle" ? "bg-[#0D121F] border-slate-800/60 text-[#64748B]" : "bg-[#06B6D4]/10 border-[#06B6D4]/20 text-[#06B6D4]"}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${globalStatus === "completed" ? "bg-[#22C55E]" : globalStatus === "failed" ? "bg-[#EF4444]" : globalStatus === "idle" ? "bg-[#64748B]" : "bg-[#06B6D4] animate-pulse"}`} />
            {globalStatus === "idle" ? "Idle" : globalStatus === "completed" ? "Completed" : globalStatus === "failed" ? "Failed" : "Running…"}
          </span>
          <Button variant="ghost" size="icon" className="h-7 w-7 rounded-lg bg-[#0D121F] border border-slate-800/60 hover:bg-slate-800/60" onClick={onClose} aria-label="Close"><X size={14} /></Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="p-4 border-b border-slate-800/60 bg-[#0D121F]">
          <div className="text-[12px] font-semibold tracking-[0.06em] text-[#64748B] uppercase">Planner Task</div>
          <div className="text-sm font-semibold text-[#F8FAFC] mt-1 truncate">{plannerDetails?.goal ?? (globalStatus === "idle" ? "No active task — send a query" : "Waiting for planner…")}</div>
          <div className="flex gap-1.5 mt-2 flex-wrap">
            {(plannerDetails?.capabilities ?? (globalStatus === "idle" ? [] : ["awaiting planner"])).slice(0, 3).map(c => (
              <span key={c} className="rounded-full bg-[#0D121F] border border-slate-800/60 px-2 py-1 text-[11px] text-slate-400 font-mono truncate max-w-[180px] inline-block">{c}</span>
            ))}
          </div>
          <div className="text-xs text-[#64748B] mt-2 flex items-center gap-1.5"><Clock3 size={10} /> {fmt(now)} · {plannerDetails?.llm ?? "qwen-3.5-9b"} · {plannerDetails?.spatial_target ?? "AOI pending"}</div>
          {plannerDetails?.coreference_resolved ? (
            <div className="mt-2 rounded-lg bg-[#090D14]/50 border border-slate-800/60 px-2.5 py-2">
              <div className="text-[11px] text-[#94A3B8]">We noticed you meant <span className="text-[#F8FAFC]">the water body from your last question</span> — so we’ll zoom right in there.</div>
              <details className="mt-1.5 group">
                <summary className="text-[10px] font-mono text-[#475569] cursor-pointer hover:text-[#64748B]">Show technical details</summary>
                <div className="mt-1 text-[10px] font-mono text-[#06B6D4]">coreference: {plannerDetails.coreference_resolved}</div>
                {plannerDetails.crop_target && <div className="text-[10px] font-mono text-[#94A3B8]">crop: [{plannerDetails.crop_target.join(", ")}] → new tile</div>}
              </details>
            </div>
          ) : null}
        </div>

        <div className="p-4 space-y-6">
          <div>
            <div className="flex items-center justify-between mb-1">
              <div className="text-[12px] font-semibold tracking-[0.06em] text-[#64748B] uppercase">Planner Timeline</div>
              <span className="text-[11px] font-mono text-slate-500">{plannerTasks.length ? `${plannerTasks.length} tasks` : "—"}</span>
            </div>
            <div className="text-[11px] text-[#475569] mb-3">LLM planner assigned • {plannerDetails ? "live" : "waiting"}</div>
            {plannerTasks.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-800/60 bg-[#0D121F]/30 p-4 text-center">
                <div className="text-xs text-[#64748B]">{globalStatus === "idle" ? "No tasks yet — send a query" : "Planner is deciding tasks…"}</div>
                <div className="text-[11px] text-[#475569] mt-1">Timeline will appear once Qwen assigns work</div>
              </div>
            ) : (
              <div className="relative pl-7">
                <div className="absolute left-[11px] top-2 bottom-8 w-px bg-slate-800/60" />
                {plannerTasks.map((task) => (
                  <div key={task.id} className="relative flex gap-3 pb-6 last:pb-0">
                    <span
                      className={`absolute left-0 top-1 h-5 w-5 rounded-full border-2 grid place-items-center bg-[#0D121F] shrink-0 ${
                        task.status === "completed" ? "border-[#22C55E] bg-[#22C55E]/10" : task.status === "running" ? "border-[#06B6D4] bg-[#06B6D4]/10" : task.status === "failed" ? "border-[#EF4444] bg-[#EF4444]/10" : "border-slate-700 bg-slate-800/40"
                      }`}
                    >
                      {task.status === "completed" ? (
                        <Check size={10} className="text-[#22C55E]" />
                      ) : task.status === "running" ? (
                        <Loader2 size={10} className="text-[#06B6D4] animate-spin" />
                      ) : task.status === "failed" ? (
                        <X size={10} className="text-[#EF4444]" />
                      ) : (
                        <CircleDot size={10} className="text-slate-600" />
                      )}
                    </span>
                    <div className="flex-1 min-w-0 ml-1 rounded-lg border border-slate-800/60 bg-[#0D121F]/50 px-3 py-2.5">
                      <div className="text-[13px] font-medium capitalize truncate" style={{ color: task.status === "completed" || task.status === "running" ? "#F8FAFC" : "#94A3B8" }}>
                        {task.title}
                      </div>
                      <div className="text-[11px] text-[#64748B] truncate font-mono">{task.subtitle}</div>
                      <div className="flex items-center gap-2 mt-1.5">
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${task.status === "completed" ? "bg-[#22C55E]/10 text-[#22C55E]" : task.status === "running" ? "bg-[#06B6D4]/10 text-[#06B6D4] animate-pulse" : task.status === "failed" ? "bg-[#EF4444]/10 text-[#EF4444]" : "bg-slate-800/60 text-slate-500"}`}>
                          {task.status.toUpperCase()}
                        </span>
                        {task.durationMs !== undefined && <span className="text-[10px] font-mono text-slate-500">{task.durationMs}ms</span>}
                        {task.status === "running" && <span className="text-[10px] text-slate-500">running…</span>}
                      </div>
                    </div>
                  </div>
                ))}
                {allCompleted && (
                  <div className="relative flex gap-3 pt-1">
                    <span className="absolute left-0 top-1 h-5 w-5 rounded-full bg-[#06B6D4] border-2 border-[#06B6D4] grid place-items-center shrink-0">
                      <Check size={10} className="text-white" />
                    </span>
                    <div className="flex-1 ml-1 rounded-lg bg-[#06B6D4]/10 border border-[#06B6D4]/20 px-3 py-2.5">
                      <div className="text-xs font-semibold text-[#06B6D4]">Process completed</div>
                      <div className="text-[11px] text-slate-400 mt-0.5">Ran for {totalMs > 0 ? `${totalMs}ms${totalMs > 1000 ? ` • ${(totalMs / 1000).toFixed(1)}s` : ""}` : "—"} • {plannerTasks.length} tasks • {new Date().toLocaleTimeString()}</div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="rounded-lg bg-[#0D121F] border border-slate-800/60 px-3 py-2.5 flex items-center justify-between h-[42px]">
            <span className="text-xs text-[#94A3B8]">Status</span>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium" style={{ color: globalStatus === "completed" ? "#22C55E" : globalStatus === "failed" ? "#EF4444" : "#F8FAFC" }}>
              <span className={`h-2 w-2 rounded-full ${globalStatus === "completed" ? "bg-[#22C55E]" : globalStatus === "failed" ? "bg-[#EF4444]" : globalStatus === "idle" ? "bg-[#64748B]" : "bg-[#06B6D4] animate-pulse"}`} />
              {globalStatus === "completed" ? "Completed" : globalStatus === "failed" ? "Failed" : globalStatus === "idle" ? "Idle" : "Running"}
            </span>
          </div>

          <div>
            <div className="text-[12px] font-semibold tracking-[0.06em] text-[#64748B] uppercase mb-2">Artifacts · {artifacts.length}</div>
            <div className="flex gap-1.5 mb-3 flex-wrap">
              {["chart", "table", "map"].map(a => (
                <span key={a} className="inline-flex items-center gap-1.5 rounded-full border border-slate-800/60 bg-[#0D121F] px-2.5 py-1 text-xs text-[#94A3B8]">
                  <span className={`w-1.5 h-1.5 rounded-full ${a === "chart" ? "bg-[#06B6D4]" : a === "table" ? "bg-[#22C55E]" : "bg-[#F59E0B]"}`} /> {a}
                </span>
              ))}
            </div>
            {artifacts.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-800/60 bg-[#0D121F]/30 p-6 text-center">
                <div className="text-xs text-[#64748B]">No artifacts generated</div>
                <div className="text-[11px] text-[#475569] mt-1">Run a query to generate evidence — charts, tables, and maps will appear here</div>
              </div>
            ) : (
              <div className="space-y-2">
                {artifacts.slice(0, 3).map(a => (
                  <div key={a.id} className="rounded-lg border border-slate-800/60 bg-[#0D121F] p-3 hover:border-slate-800/60 transition-colors">
                    <div className="text-xs text-[#F8FAFC] line-clamp-2 leading-relaxed">{a.content.slice(0, 100)}…</div>
                    <div className="flex gap-1.5 mt-2 flex-wrap">
                      {a.content.includes("```chart") && <span className="inline-flex items-center gap-1.5 max-w-[180px] bg-[#0D121F] border border-slate-800/60 text-[#94A3B8] rounded-lg px-2 py-1 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-[#06B6D4]" /> <span className="truncate">chart</span></span>}
                      {a.content.includes("|") && <span className="inline-flex items-center gap-1.5 max-w-[180px] bg-[#0D121F] border border-slate-800/60 text-[#94A3B8] rounded-lg px-2 py-1 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" /> <span className="truncate">table</span></span>}
                      {(a.content.includes("comparison:") || a.content.includes("map:") || a.content.includes("image:") || a.content.includes("gallery:")) && <span className="inline-flex items-center gap-1.5 max-w-[180px] bg-[#0D121F] border border-slate-800/60 text-[#94A3B8] rounded-lg px-2 py-1 text-xs"><span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" /> <span className="truncate">map</span></span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {isInspection && (
            <div className="rounded-lg border border-slate-800/60 bg-[#0D121F] overflow-hidden">
              <div className="px-3 py-2.5 border-b border-slate-800/60 flex items-center justify-between bg-[#0D121F]">
                <span className="text-xs font-semibold tracking-[0.06em] text-[#94A3B8]">INSPECTION</span>
                <span className="text-[11px] font-medium text-[#22C55E]">{selected ? `${Math.round((selected.confidence ?? 0.87)*100)}% High` : "—"}</span>
              </div>
              <div className="p-3 space-y-3">
                <div className="relative aspect-[4/3] rounded-lg overflow-hidden bg-[#090D14] border border-slate-800/60">
                  {!previewLoaded && <ImageCardSkeleton aspectRatio="4/3" />}
                  <div className={`h-full w-full grid place-items-center bg-gradient-to-br from-slate-800/60 to-[#090D14] transition-opacity duration-200 ${previewLoaded ? "opacity-0 absolute inset-0 pointer-events-none" : "opacity-100"}`} aria-hidden>
                    <span className="text-[11px] font-mono text-slate-500">5120×5120 · 10 m GSD · Sentinel-2</span>
                  </div>
                  <div className="absolute inset-4 border border-white/60 shadow-[0_0_0_1px_rgba(0,0,0,0.5)] rounded-sm pointer-events-none" />
                  <div className="absolute bottom-2 left-2 rounded-md bg-[#090D14]/70 backdrop-blur border border-slate-800/60 px-2 py-1 text-[11px] text-white">5120×5120 · 10.0 m/px</div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold tracking-[0.06em] text-[#64748B] uppercase mb-1.5">Metadata</div>
                  <div className="rounded-lg bg-[#090D14] border border-slate-800/60 divide-y divide-[#1E293B] text-xs">
                    {[
                      ["CRS", "EPSG:32617 (WGS 84 / UTM zone 17N)"],
                      ["Extent", "5120 × 5120 px"],
                      ["Resolution", "10.0 m/px"],
                      ["Acquired", "2018-09-12 · 15:42:11 UTC"],
                      ["Platform", "Sentinel-2B"],
                      ["Product", "S2B_MSIL2A_..."],
                      ["Cloud Cover", "12.4%"],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between px-2.5 py-1.5">
                        <span className="text-[#64748B]">{k}</span>
                        <span className="text-[#94A3B8] font-mono text-[11px]">{v ?? "—"}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold tracking-[0.06em] text-[#64748B] uppercase">Bands</div>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {["B02 Blue", "B03 Green", "B04 Red", "B08 NIR"].map(b => (
                      <span key={b} className="inline-flex items-center gap-1 rounded-full bg-[#0D121F] border border-slate-800/60 px-2 py-1 text-[11px] text-[#94A3B8]">{b}</span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[11px] font-semibold tracking-[0.06em] text-[#64748B] uppercase">Analysis Confidence</div>
                  <div className="mt-1.5 h-1.5 w-full rounded-full bg-[#090D14] border border-slate-800/60 overflow-hidden">
                    <div className="h-full bg-gradient-to-r from-[#22C55E] to-[#06B6D4] rounded-full transition-all duration-500" style={{ width: selected ? `${Math.round((selected.confidence ?? 0.87)*100)}%` : "0%" }} />
                  </div>
                  <div className="flex justify-between mt-1 text-[11px] text-[#64748B]"><span>Low 0.2</span><span>0.5</span><span>0.8 High</span></div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

