import { ShieldCheck, Brain, Satellite, Search, BadgeCheck, Sparkles, ArrowRight } from "lucide-react";
import { useExecutionStore } from "@/store/execution.store";

const ABSTRACT_STEPS = [
  { id: "input", title: "Securing your request", desc: "Checking where you’re looking", icon: ShieldCheck },
  { id: "planner", title: "Understanding your question", desc: "Figuring out what you need", icon: Brain },
  { id: "models", title: "Analyzing from space", desc: "Our AI looks at the imagery", icon: Satellite },
  { id: "evidence", title: "Verifying the evidence", desc: "Making sure it’s really there", icon: Search },
  { id: "composer", title: "Crafting your answer", desc: "Writing a clear, grounded reply", icon: Sparkles },
] as const;

export function AbstractIntelligenceLoop({ activeId }: { activeId?: string }) {
  const { pipelineSteps } = useExecutionStore();
  const getStatus = (id: string) => pipelineSteps.find(s => s.id === id)?.status ?? "pending";

  return (
    <div className="w-full max-w-[720px] mx-auto">
      <div className="flex items-center justify-between gap-2">
        {ABSTRACT_STEPS.map((step, idx) => {
          const status = getStatus(step.id);
          const isActive = status === "running";
          const isDone = status === "completed";
          const isPending = status === "pending";
          return (
            <div key={step.id} className="flex items-center gap-2 flex-1">
              <div className="flex flex-col items-center gap-1.5 flex-1 min-w-0">
                <div
                  className={`h-8 w-8 rounded-full grid place-items-center border text-xs transition-all ${
                    isDone
                      ? "bg-[#22C55E] border-[#22C55E] text-white shadow-[0_0_12px_rgba(34,197,94,0.4)]"
                      : isActive
                      ? "bg-[#090D14] border-[#06B6D4] text-[#60A5FA] shadow-[0_0_16px_rgba(6,182,212,0.5)] animate-pulse"
                      : "bg-[#0D121F] border-slate-800/60 text-[#475569]"
                  }`}
                >
                  {isDone ? <BadgeCheck size={14} /> : <step.icon size={13} />}
                </div>
                <div className="text-center">
                  <div className={`text-[11px] font-medium leading-tight truncate ${isDone || isActive ? "text-[#F8FAFC]" : "text-[#64748B]"}`}>{step.title}</div>
                  <div className="text-[11px] text-[#475569] hidden sm:block truncate">{step.desc}</div>
                </div>
                <div className={`h-1 w-1 rounded-full ${isDone ? "bg-[#22C55E]" : isActive ? "bg-[#06B6D4] animate-pulse" : "bg-[#334155]"}`} />
              </div>
              {idx < ABSTRACT_STEPS.length - 1 && (
                <ArrowRight size={12} className={`shrink-0 hidden sm:block ${pipelineSteps[idx]?.status === "completed" ? "text-[#22C55E]/60" : "text-[#334155]"}`} />
              )}
            </div>
          );
        })}
      </div>
      <div className="mt-3 text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#0D121F]/80 border border-slate-800/60 px-3 py-1 text-[11px] text-[#94A3B8] backdrop-blur">
          <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E] animate-pulse" />
          Not one giant AI — a controlled investigation. Each step checks the last.
        </span>
      </div>
    </div>
  );
}

export function InlineAbstractStatus() {
  const { pipelineSteps, globalStatus } = useExecutionStore();
  const active = pipelineSteps.find(s => s.status === "running");
  if (!active) {
    if (globalStatus === "completed") return <span className="inline-flex items-center gap-1.5 text-xs text-[#22C55E]"><span className="h-1.5 w-1.5 rounded-full bg-[#22C55E]" /> Investigation complete — answer grounded in evidence</span>;
    if (globalStatus === "idle") return <span className="text-xs text-[#64748B]">Ready to investigate</span>;
    return null;
  }
  const friendly: Record<string, string> = {
    input: "Securing your request…",
    planner: "Understanding what you’re asking…",
    models: "Analyzing the imagery from space…",
    evidence: "Verifying the evidence…",
    composer: "Crafting your answer…",
  };
  return (
    <span className="inline-flex items-center gap-2 text-xs text-[#93C5FD]">
      <span className="h-3 w-3 rounded-full border border-[#06B6D4]/30 border-t-[#60A5FA] animate-spin" />
      {friendly[active.id] ?? "Working…"}
    </span>
  );
}
