import { useEffect, useState } from "react";
import {
  FileJson, Layers, ShieldCheck, PenLine, ChevronDown,
  Check, Loader2, CircleDot, Cpu, GitBranch, Sparkles,
} from "lucide-react";
import { useExecutionStore } from "@/store/execution.store";
import { cn } from "@/lib/utils";
import type { ModelExecutionState } from "@/schemas/execution";
import { motion, AnimatePresence } from "framer-motion";

type Stage = {
  key: "planner" | "models" | "evidence" | "composer";
  label: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  status: ModelExecutionState;
  detail?: string;
};

function tone(status: ModelExecutionState) {
  if (status === "completed") return "bg-emerald-500/15 border-emerald-500/20 text-emerald-400";
  if (status === "running") return "bg-[#38D6FF]/10 border-[#38D6FF]/20 text-[#38D6FF]";
  if (status === "failed") return "bg-red-500/15 border-red-500/20 text-red-400";
  return "bg-white/5 border-white/10 text-white/30";
}

const THINKING_BY_STAGE: Record<string, string[]> = {
  planner: ["Musing over capabilities", "Planning the route", "Choosing the right models"],
  models: ["Sifting through Sentinel tiles", "Grounding detections", "Fusing optical & SAR", "Tracing change signals"],
  evidence: ["Weaving the evidence graph", "Calibrating confidence", "Cross-checking sources"],
  composer: ["Drafting the answer", "Composing final response", "Weaving narrative & evidence"],
};

export function ActivityStream({ streaming, summary }: { streaming: boolean; summary?: string }) {
  const { plannerStatus, modelStatus, evidenceStatus, composerStatus, plannerDetails, modelDetails } = useExecutionStore();
  const [open, setOpen] = useState(streaming);
  const [phraseIdx, setPhraseIdx] = useState(0);

  useEffect(() => {
    if (streaming) setOpen(true);
    else setOpen(false);
  }, [streaming]);

  const stages: Stage[] = [
    { key: "planner", label: "Plan", icon: FileJson, status: plannerStatus, detail: plannerDetails?.goal },
    { key: "models", label: "Models", icon: Layers, status: modelStatus, detail: modelDetails?.activeModels?.join(" · ") },
    { key: "evidence", label: "Evidence", icon: ShieldCheck, status: evidenceStatus },
    { key: "composer", label: "Compose", icon: PenLine, status: composerStatus },
  ];

  const done = stages.filter((s) => s.status === "completed").length;
  const active = stages.find((s) => s.status === "running");
  const failed = stages.some((s) => s.status === "failed");
  const pct = Math.round((done / stages.length) * 100);

  const activePhrases = active ? (THINKING_BY_STAGE[active.key] ?? ["Thinking"]) : [];
  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setPhraseIdx(i => (i + 1) % activePhrases.length), 1450);
    return () => clearInterval(id);
  }, [active?.key, activePhrases.length]);

  const compactLabel = failed
    ? "Execution failed — see details"
    : active
      ? activePhrases[phraseIdx % activePhrases.length]
      : summary ?? `Planned · ${modelDetails?.activeModels?.length ?? 2} models · evidence gathered`;

  return (
    <div className="mt-3 rounded-xl border border-white/[0.06] bg-[#050A14]/60 backdrop-blur overflow-hidden">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2.5 px-3 py-2.5 text-left group"
        aria-expanded={open}
      >
        {active ? (
          <span className="h-5 w-5 rounded-full bg-[#38D6FF]/10 border border-[#38D6FF]/20 grid place-items-center shrink-0">
            <Loader2 size={12} className="text-[#38D6FF] animate-spin" />
          </span>
        ) : failed ? (
          <span className="h-5 w-5 rounded-full bg-red-500/10 border border-red-500/20 grid place-items-center shrink-0">
            <CircleDot size={12} className="text-red-400" />
          </span>
        ) : (
          <span className="h-5 w-5 rounded-full bg-emerald-500/10 border border-emerald-500/20 grid place-items-center shrink-0">
            <Check size={12} className="text-emerald-400" />
          </span>
        )}

        <div className="flex-1 min-w-0 flex items-center gap-2">
          {active ? (
            <AnimatePresence mode="wait">
              <motion.span
                key={phraseIdx}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -4 }}
                transition={{ duration: 0.22 }}
                className="text-[11px] font-medium tracking-wide text-[#38D6FF] italic"
              >
                {compactLabel}…
              </motion.span>
            </AnimatePresence>
          ) : (
            <span className={cn("text-[11px] font-medium tracking-wide", failed ? "text-red-400" : "text-white/55")}>
              {compactLabel}
            </span>
          )}
          {active && <span className="h-1 w-1 rounded-full bg-[#38D6FF] animate-pulse" />}
        </div>

        {!failed && !active && (
          <span className="h-1 flex-1 max-w-[100px] rounded-full bg-white/5 overflow-hidden hidden sm:block">
            <span className="block h-full bg-[#38D6FF]/60 transition-all duration-500" style={{ width: `${pct}%` }} />
          </span>
        )}
        <ChevronDown size={13} className={cn("text-white/30 shrink-0 transition-transform", open && "rotate-180")} />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.25, 0.1, 0.25, 1] }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 pt-1 space-y-1.5 border-t border-white/[0.06]">
              {stages.map((s) => (
                <div key={s.key} className="flex items-center gap-2.5 py-1">
                  <span className={cn("h-6 w-6 rounded-xl grid place-items-center border shrink-0", tone(s.status))}>
                    {s.status === "completed" ? <Check size={11} /> : s.status === "running" ? <Loader2 size={11} className="animate-spin" /> : s.status === "failed" ? <CircleDot size={11} /> : <CircleDot size={11} />}
                  </span>
                  <span className={cn("text-xs font-medium w-16 shrink-0", s.status === "completed" ? "text-white/80" : s.status === "running" ? "text-[#38D6FF]" : "text-white/35")}>
                    {s.label}
                  </span>
                  <span className="text-[11px] text-white/40 truncate flex-1">
                    {s.status === "completed" ? s.detail ?? "done" : s.status === "running" ? s.detail ?? "in progress" : s.status === "failed" ? "failed" : "queued"}
                  </span>
                  <span className="text-[10px] font-mono text-white/25 uppercase">{s.status}</span>
                </div>
              ))}
              {plannerDetails?.capabilities?.length ? (
                <div className="flex flex-wrap gap-1 pt-1.5">
                  {plannerDetails.capabilities.map((c) => (
                    <span key={c} className="inline-flex items-center gap-1 rounded-full border border-white/10 bg-[#02070D] px-2 py-0.5 text-[10px] text-white/50 font-mono">
                      <GitBranch size={9} className="text-[#38D6FF]/60" /> {c}
                    </span>
                  ))}
                </div>
              ) : null}
              {modelDetails?.activeModels?.length ? (
                <div className="flex items-center gap-1.5 pt-1 text-[10px] text-white/35 font-mono">
                  <Cpu size={10} className="text-[#38D6FF]/60" />
                  {modelDetails.activeModels.join(" · ")}
                </div>
              ) : null}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

