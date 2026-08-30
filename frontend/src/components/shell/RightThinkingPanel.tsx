import { useEffect, useState } from "react";
import { X, Clock3, Check, Loader2, CircleDot, Sparkles, Layers, Satellite, ShieldCheck, Cpu } from "lucide-react";
import { useExecutionStore } from "@/store/execution.store";
import { useChatStore } from "@/store/chat.store";
import { Button } from "@/components/ui/button";
import { useMapStore } from "@/store/map.store";
import { ImageCardSkeleton } from "@/components/ui/skeleton";

function fmt(ts?: number) {
  if (!ts) return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// ── Section label with left accent when active ─────────────────────────
function SectionLabel({
  label,
  count,
  active,
  icon: Icon,
}: {
  label: string;
  count?: string | number;
  active?: boolean;
  icon?: React.ComponentType<{ size?: number; className?: string }>;
}) {
  return (
    <div className={`flex items-center justify-between ${active ? "pl-2.5 -ml-2.5 border-l-2 border-[#06B6D4]" : ""}`}>
      <span className={`flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.09em] uppercase ${active ? "text-slate-200" : "text-slate-500"}`}>
        {Icon && <Icon size={11} className={active ? "text-[#06B6D4]" : "text-slate-600"} />}
        {label}
      </span>
      {count !== undefined && (
        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full border ${active ? "bg-[#06B6D4]/10 border-[#06B6D4]/20 text-[#06B6D4]" : "bg-[#101827] border-slate-700/40 text-slate-600"}`}>
          {count}
        </span>
      )}
    </div>
  );
}

export function RightThinkingPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { globalStatus, pipelineSteps, plannerDetails, stepStartedAt } = useExecutionStore();
  const { messages } = useChatStore();
  const { selectedFeatureId, features } = useMapStore();
  const [now, setNow] = useState(Date.now());
  const running = !["completed", "failed", "cancelled", "idle"].includes(globalStatus);
  useEffect(() => {
    if (!running) return; // freeze the clock once the run is terminal
    const id = setInterval(() => setNow(Date.now()), 150);
    return () => clearInterval(id);
  }, [running]);
  const selected = features.find((f) => f.id === selectedFeatureId);
  const isInspection = !!selected;
  const artifacts = messages.filter(
    (m) =>
      m.role === "assistant" &&
      (m.content.includes("```") ||
        m.content.includes("|") ||
        m.content.includes("comparison:") ||
        m.content.includes("map:") ||
        m.content.includes("image:"))
  );

  const [previewLoaded, setPreviewLoaded] = useState(false);
  useEffect(() => {
    setPreviewLoaded(false);
  }, [selectedFeatureId]);

  // Planner-driven timeline
  const plannerTasks = (() => {
    if (!plannerDetails?.task_router_map || Object.keys(plannerDetails.task_router_map).length === 0) {
      if (globalStatus === "idle") return [] as { id: string; title: string; subtitle: string; status: string; durationMs?: number }[];
      return pipelineSteps.map((s) => ({
        id: s.id,
        title: s.title,
        subtitle: s.subtitle ?? "",
        status: s.status,
        durationMs: s.durationMs,
      }));
    }
    const getStatus = (key: string) => {
      const k = key.toLowerCase();
      if (k.includes("crop") || k.includes("gis") || k.includes("raster")) {
        return (
          pipelineSteps.find((p) => p.id === "preparing")?.status ??
          (globalStatus === "completed" ? "completed" : globalStatus === "idle" ? "pending" : "running")
        );
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
  const timelineActive = globalStatus !== "idle" && globalStatus !== "completed";

  if (!open) return null;

  return (
    <div className="w-[360px] h-full bg-[#0B1120] flex flex-col overflow-hidden">
      {/* ── Header ── */}
      <div className="h-12 shrink-0 sticky top-0 z-10 flex items-center justify-between px-4 border-b border-slate-800/50 bg-[#0B1120]">
        <span className="text-[11px] font-semibold tracking-[0.1em] uppercase text-slate-200 flex items-center gap-2">
          <span className={`h-6 w-6 rounded-md grid place-items-center border ${isInspection ? "bg-[#F59E0B]/10 border-[#F59E0B]/20 text-[#F59E0B]" : "bg-[#06B6D4]/10 border-[#06B6D4]/20 text-[#06B6D4]"}`}>
            {isInspection ? <Cpu size={12} /> : <Satellite size={12} />}
          </span>
          {isInspection ? "Inspection" : "Pipeline"}
        </span>
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium border ${
              globalStatus === "completed"
                ? "bg-[#22C55E]/10 border-[#22C55E]/20 text-[#22C55E]"
                : globalStatus === "failed"
                  ? "bg-[#EF4444]/10 border-[#EF4444]/20 text-[#EF4444]"
                  : globalStatus === "idle"
                    ? "bg-[#101827] border-slate-700/40 text-slate-500"
                    : "bg-[#06B6D4]/10 border-[#06B6D4]/20 text-[#06B6D4]"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                globalStatus === "completed"
                  ? "bg-[#22C55E]"
                  : globalStatus === "failed"
                    ? "bg-[#EF4444]"
                    : globalStatus === "idle"
                      ? "bg-[#475569]"
                      : "bg-[#06B6D4] animate-pulse"
              }`}
              style={globalStatus !== "idle" && globalStatus !== "failed" && globalStatus !== "completed" ? { boxShadow: "0 0 6px #06B6D4" } : undefined}
            />
            {globalStatus === "idle" ? "Idle" : globalStatus === "completed" ? "Completed" : globalStatus === "failed" ? "Failed" : "Running"}
          </span>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 rounded-lg bg-[#101827] border border-slate-700/40 hover:bg-[#141F30] hover:border-slate-600/40 text-slate-500 hover:text-slate-200"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={14} />
          </Button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* ── Planner Task card ── elevated surface ── */}
        <div className="p-4 border-b border-slate-800/40 bg-[#0B1120]">
          <div className="rounded-xl border border-slate-700/40 bg-[#101827] overflow-hidden" style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.35)" }}>
            <div className="px-3.5 py-3">
              <SectionLabel label="Planner Task" active={globalStatus !== "idle"} icon={Sparkles} />
              <div className="text-[13px] font-semibold text-slate-100 mt-2 leading-snug truncate">
                {plannerDetails?.goal ?? (globalStatus === "idle" ? "No active task — send a query" : "Waiting for planner…")}
              </div>
              <div className="flex gap-1.5 mt-2 flex-wrap">
                {(plannerDetails?.capabilities ?? (globalStatus === "idle" ? [] : ["awaiting planner"])).slice(0, 3).map((c) => (
                  <span key={c} className="rounded-full bg-[#0B1120] border border-slate-700/40 px-2.5 py-1 text-[11px] text-slate-400 font-mono truncate max-w-[180px] inline-block">
                    {c}
                  </span>
                ))}
              </div>
              <div className="text-[11px] text-slate-600 mt-2.5 flex items-center gap-1.5 font-mono">
                <Clock3 size={10} className="text-slate-500" /> {fmt(now)} · {plannerDetails?.llm ?? "qwen-3.5-9b"} · {plannerDetails?.spatial_target ?? "AOI pending"}
              </div>
            </div>
            {plannerDetails?.coreference_resolved ? (
              <div className="mx-3.5 mb-3 rounded-lg bg-[#05080F]/60 border border-slate-800/50 px-3 py-2.5">
                <div className="text-[11px] leading-relaxed text-slate-400">
                  We noticed you meant <span className="text-slate-100 font-medium">the water body from your last question</span> — so we’ll zoom right in there.
                </div>
                <details className="mt-2 group">
                  <summary className="text-[10px] font-mono text-slate-600 cursor-pointer hover:text-slate-400 transition-colors">
                    Show technical details
                  </summary>
                  <div className="mt-1.5 text-[10px] font-mono text-[#06B6D4]">coreference: {plannerDetails.coreference_resolved}</div>
                  {plannerDetails.crop_target && (
                    <div className="text-[10px] font-mono text-slate-500 mt-1">crop: [{plannerDetails.crop_target.join(", ")}] → new tile</div>
                  )}
                </details>
              </div>
            ) : null}
          </div>
        </div>

        <div className="p-4 space-y-6">
          {/* ── Timeline ── */}
          <div>
            <SectionLabel label="Planner Timeline" count={plannerTasks.length ? `${plannerTasks.length} tasks` : "—"} active={timelineActive} icon={Layers} />
            <div className="text-[11px] text-slate-600 mt-1 mb-3 font-mono">LLM planner assigned · {plannerDetails ? "live" : "waiting"}</div>
            {plannerTasks.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-700/40 bg-[#101827]/40 p-5 text-center">
                <div className="h-8 w-8 rounded-lg bg-[#05080F] border border-slate-800/50 grid place-items-center mx-auto mb-2">
                  <Layers size={14} className="text-slate-600" />
                </div>
                <div className="text-xs font-medium text-slate-400">{globalStatus === "idle" ? "No tasks yet — send a query" : "Planner is deciding tasks…"}</div>
                <div className="text-[11px] text-slate-600 mt-1">Timeline will appear once Qwen assigns work</div>
              </div>
            ) : (
              <div className="relative pl-7">
                <div className="absolute left-[11px] top-2 bottom-8 w-px bg-slate-700/30" />
                {plannerTasks.map((task) => (
                  <div key={task.id} className="relative flex gap-3 pb-5 last:pb-0">
                    <span
                      className={`absolute left-0 top-1 h-5 w-5 rounded-full border-2 grid place-items-center shrink-0 transition-colors ${
                        task.status === "completed"
                          ? "border-[#22C55E] bg-[#22C55E]/15 shadow-[0_0_8px_rgba(34,197,94,0.3)]"
                          : task.status === "running"
                            ? "border-[#06B6D4] bg-[#06B6D4]/15 shadow-[0_0_8px_rgba(6,182,212,0.3)]"
                            : task.status === "failed"
                              ? "border-[#EF4444] bg-[#EF4444]/15"
                              : "border-slate-600 bg-[#101827]"
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
                    <div className="flex-1 min-w-0 ml-1 rounded-xl border border-slate-700/40 bg-[#101827] px-3 py-2.5 hover:border-slate-600/40 hover:bg-[#141F30] transition-colors">
                      <div
                        className="text-[13px] font-medium capitalize truncate"
                        style={{ color: task.status === "completed" || task.status === "running" ? "#F1F5F9" : "#94A3B8" }}
                      >
                        {task.title}
                      </div>
                      <div className="text-[11px] text-slate-500 truncate font-mono mt-0.5">{task.subtitle}</div>
                      <div className="flex items-center gap-2 mt-2">
                        <span
                          className={`text-[10px] font-mono px-1.5 py-0.5 rounded-full border font-medium ${
                            task.status === "completed"
                              ? "bg-[#22C55E]/10 text-[#22C55E] border-[#22C55E]/20"
                              : task.status === "running"
                                ? "bg-[#06B6D4]/10 text-[#06B6D4] border-[#06B6D4]/20 animate-pulse"
                                : task.status === "failed"
                                  ? "bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]/20"
                                  : "bg-[#0B1120] text-slate-500 border-slate-700/40"
                          }`}
                        >
                          {task.status.toUpperCase()}
                        </span>
                        {task.status === "running" ? (
                          <span className="text-[10px] font-mono text-[#06B6D4]">
                            {(() => {
                              const started = (stepStartedAt as any)[task.id] ?? (task.id === "change_vqa" || task.id === "grounding" || task.id === "vqa" || task.id === "optical_sar_fusion" ? stepStartedAt["analyzing"] : undefined) ?? now;
                              const elapsed = Math.max(0, now - started);
                              return elapsed < 1000 ? `${elapsed}ms` : `${(elapsed / 1000).toFixed(1)}s`;
                            })()} · running…
                          </span>
                        ) : task.durationMs !== undefined ? (
                          <span className="text-[10px] font-mono text-slate-500">{task.durationMs}ms</span>
                        ) : null}
                      </div>
                    </div>
                  </div>
                ))}
                {allCompleted && (
                  <div className="relative flex gap-3 pt-1">
                    <span className="absolute left-0 top-1 h-5 w-5 rounded-full bg-[#06B6D4] border-2 border-[#06B6D4] grid place-items-center shrink-0 shadow-[0_0_12px_rgba(6,182,212,0.4)]">
                      <Check size={10} className="text-white" />
                    </span>
                    <div className="flex-1 ml-1 rounded-xl bg-[#06B6D4]/8 border border-[#06B6D4]/20 px-3 py-2.5">
                      <div className="text-xs font-semibold text-[#06B6D4]">Process completed</div>
                      <div className="text-[11px] text-slate-500 mt-0.5 font-mono">
                        Ran for {totalMs > 0 ? `${totalMs}ms${totalMs > 1000 ? ` · ${(totalMs / 1000).toFixed(1)}s` : ""}` : "—"} · {plannerTasks.length} tasks · {new Date().toLocaleTimeString()}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* ── Status pill ── */}
          <div className="rounded-xl bg-[#101827] border border-slate-700/40 px-3.5 py-3 flex items-center justify-between">
            <span className="text-[11px] font-semibold tracking-[0.07em] uppercase text-slate-500">Status</span>
            <span
              className="inline-flex items-center gap-1.5 text-xs font-medium"
              style={{ color: globalStatus === "completed" ? "#22C55E" : globalStatus === "failed" ? "#EF4444" : "#F1F5F9" }}
            >
              <span
                className={`h-2 w-2 rounded-full ${globalStatus === "completed" ? "bg-[#22C55E]" : globalStatus === "failed" ? "bg-[#EF4444]" : globalStatus === "idle" ? "bg-[#475569]" : "bg-[#06B6D4] animate-pulse"}`}
                style={globalStatus !== "idle" && globalStatus !== "completed" && globalStatus !== "failed" ? { boxShadow: "0 0 6px #06B6D4" } : undefined}
              />
              {globalStatus === "completed" ? "Completed" : globalStatus === "failed" ? "Failed" : globalStatus === "idle" ? "Idle" : "Running"}
            </span>
          </div>

          {/* ── Artifacts ── */}
          <div>
            <SectionLabel label="Artifacts" count={artifacts.length} active={artifacts.length > 0} icon={ShieldCheck} />
            <div className="flex gap-1.5 mt-3 mb-3 flex-wrap">
              {[
                { id: "chart", color: "#06B6D4" },
                { id: "table", color: "#22C55E" },
                { id: "map", color: "#F59E0B" },
              ].map((a) => (
                <span key={a.id} className="inline-flex items-center gap-1.5 rounded-full border border-slate-700/40 bg-[#101827] px-2.5 py-1 text-[11px] text-slate-400">
                  <span className="w-1.5 h-1.5 rounded-full" style={{ background: a.color, boxShadow: `0 0 6px ${a.color}60` }} /> {a.id}
                </span>
              ))}
            </div>
            {artifacts.length === 0 ? (
              <div className="rounded-xl border border-dashed border-slate-700/40 bg-[#101827]/40 p-6 text-center">
                <div className="h-8 w-8 rounded-lg bg-[#05080F] border border-slate-800/50 grid place-items-center mx-auto mb-2.5">
                  <Layers size={14} className="text-slate-600" />
                </div>
                <div className="text-xs font-medium text-slate-400">No artifacts generated</div>
                <div className="text-[11px] text-slate-600 mt-1 leading-relaxed">Run a query to generate evidence — charts, tables, and maps will appear here</div>
              </div>
            ) : (
              <div className="space-y-2">
                {artifacts.slice(0, 3).map((a) => {
                  const isChart = a.content.includes("```chart");
                  const isMap = a.content.includes("map:") || a.content.includes("comparison:") || a.content.includes("image:") || a.content.includes("gallery:");
                  return (
                  <button
                    key={a.id}
                    onClick={() => {
                      const el = document.getElementById(`msg-${a.id}`);
                      if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
                      if (isMap) {
                        // D2: map/image artifact -> ensure map visible; click will also highlight via store if bbox present
                        const bboxMatch = a.content.match(/\[([0-9.\s,]+)\]/);
                        if (bboxMatch) {
                          try { useMapStore.getState().setSelectedFeatureId(`bbox_${bboxMatch[1].replace(/\s/g,"")}`); } catch {}
                        }
                      }
                    }}
                    className="w-full text-left rounded-xl border border-slate-700/40 bg-[#101827] p-3 hover:border-slate-600/40 hover:bg-[#141F30] transition-colors group focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#06B6D4]/40"
                  >
                    <div className="flex gap-2.5">
                      {/* D2 thumbnail */}
                      <div className="h-10 w-14 rounded-lg overflow-hidden bg-[#05080F] border border-slate-700/40 shrink-0 grid place-items-center">
                        {isChart ? <span className="text-[10px] font-mono text-[#06B6D4]">▥</span> : isMap ? <span className="text-[11px]">🛰</span> : <span className="text-[10px] text-slate-500">≡</span>}
                      </div>
                      <div className="text-xs text-slate-300 line-clamp-2 leading-relaxed group-hover:text-slate-100 transition-colors flex-1">{a.content.slice(0, 90)}…</div>
                    </div>
                    <div className="flex gap-1.5 mt-2 flex-wrap">
                      {a.content.includes("```chart") && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#0B1120] border border-slate-700/40 text-slate-400 px-2.5 py-1 text-[10px] font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#06B6D4]" /> chart
                        </span>
                      )}
                      {a.content.includes("|") && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#0B1120] border border-slate-700/40 text-slate-400 px-2.5 py-1 text-[10px] font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#22C55E]" /> table
                        </span>
                      )}
                      {(a.content.includes("comparison:") || a.content.includes("map:") || a.content.includes("image:") || a.content.includes("gallery:")) && (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#0B1120] border border-slate-700/40 text-slate-400 px-2.5 py-1 text-[10px] font-medium">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#F59E0B]" /> map
                        </span>
                      )}
                    </div>
                  </button>
                  )
                })}
              </div>
            )}
          </div>

          {/* ── Inspection ── */}
          {isInspection && (
            <div className="rounded-xl border border-slate-700/40 bg-[#101827] overflow-hidden" style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.45)" }}>
              <div className="px-3.5 py-3 border-b border-slate-800/50 flex items-center justify-between bg-[#0B1120]/60">
                <span className="text-[11px] font-semibold tracking-[0.09em] uppercase text-slate-300 flex items-center gap-1.5">
                  <ShieldCheck size={12} className="text-[#22C55E]" /> Inspection
                </span>
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#22C55E]/10 border border-[#22C55E]/20 text-[#22C55E]">
                  {selected ? `${Math.round((selected.confidence ?? 0.87) * 100)}% · High` : "—"}
                </span>
              </div>
              <div className="p-3 space-y-4">
                <div className="relative aspect-[4/3] rounded-xl overflow-hidden bg-[#05080F] border border-slate-700/40">
                  {!previewLoaded && <ImageCardSkeleton aspectRatio="4/3" />}
                  <div
                    className={`h-full w-full grid place-items-center bg-gradient-to-br from-[#101827] to-[#05080F] transition-opacity duration-200 ${previewLoaded ? "opacity-0 absolute inset-0 pointer-events-none" : "opacity-100"}`}
                    aria-hidden
                  >
                    <span className="text-[11px] font-mono text-slate-600">5120×5120 · 10 m GSD · Sentinel-2</span>
                  </div>
                  <div className="absolute inset-4 border border-white/20 shadow-[0_0_0_1px_rgba(0,0,0,0.4)] rounded-sm pointer-events-none" />
                  <div className="absolute bottom-2 left-2 rounded-full bg-[#05080F]/80 backdrop-blur border border-slate-700/40 px-2.5 py-1 text-[11px] font-mono text-slate-300">
                    5120×5120 · 10.0 m/px
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.09em] uppercase text-slate-500 mb-2">Metadata</div>
                  <div className="rounded-xl bg-[#05080F] border border-slate-800/50 divide-y divide-slate-800/40 text-xs overflow-hidden">
                    {[
                      ["CRS", "EPSG:32617 (WGS 84 / UTM zone 17N)"],
                      ["Extent", "5120 × 5120 px"],
                      ["Resolution", "10.0 m/px"],
                      ["Acquired", "2018-09-12 · 15:42:11 UTC"],
                      ["Platform", "Sentinel-2B"],
                      ["Product", "S2B_MSIL2A_..."],
                      ["Cloud Cover", "12.4%"],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between px-3 py-2">
                        <span className="text-slate-500">{k}</span>
                        <span className="text-slate-400 font-mono text-[11px]">{v ?? "—"}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.09em] uppercase text-slate-500">Bands</div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {["B02 Blue", "B03 Green", "B04 Red", "B08 NIR"].map((b) => (
                      <span key={b} className="inline-flex items-center gap-1 rounded-full bg-[#0B1120] border border-slate-700/40 px-2.5 py-1 text-[11px] text-slate-400">
                        {b}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] font-semibold tracking-[0.09em] uppercase text-slate-500">Analysis Confidence</div>
                  <div className="mt-2 h-2 w-full rounded-full bg-[#05080F] border border-slate-800/50 overflow-hidden p-0.5">
                    <div
                      className="h-full bg-gradient-to-r from-[#22C55E] to-[#06B6D4] rounded-full transition-all duration-700"
                      style={{ width: selected ? `${Math.round((selected.confidence ?? 0.87) * 100)}%` : "0%" }}
                    />
                  </div>
                  <div className="flex justify-between mt-1.5 text-[10px] font-mono text-slate-600">
                    <span>Low 0.2</span>
                    <span>0.5</span>
                    <span className="text-[#22C55E] font-medium">0.8 High</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
