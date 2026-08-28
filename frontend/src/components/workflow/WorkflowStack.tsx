import { MessageSquare, Shield, Brain, Cpu, Layers, Database, GitBranch, Satellite, ScanSearch, Sparkles } from "lucide-react";
import { useExecutionStore } from "@/store/execution.store";
import { useSessionStore } from "@/store/session.store";

const layers = [
  {
    id: "user",
    title: "USER",
    subtitle: "Map viewer · Chat · Session state",
    icon: MessageSquare,
    color: "text-slate-300",
    dot: "bg-slate-400",
  },
  {
    id: "gateway",
    title: "GATEWAY",
    subtitle: "API gateway + auth · Rate limiting · JWT · session routing",
    icon: Shield,
    color: "text-slate-300",
    dot: "bg-slate-500",
  },
  {
    id: "planner",
    title: "PLANNER",
    subtitle: "Qwen 3.5 9B · Coreference · goal plan JSON · crop coords",
    icon: Brain,
    color: "text-cyan-400",
    dot: "bg-cyan-400",
    highlight: true,
  },
  {
    id: "execution",
    title: "EXECUTION",
    subtitle: "GIS/rasterio · Task router · Spatial store",
    icon: Cpu,
    color: "text-slate-300",
    dot: "bg-slate-400",
    children: [
      { label: "GIS/rasterio engine", sub: "Crop · reproject · tile" },
      { label: "Task router", sub: "Maps goals → model calls" },
      { label: "Spatial state store", sub: "BBoxes · masks · history" },
    ],
  },
  {
    id: "models",
    title: "MODELS",
    subtitle: "Stateless perception — Qwen reasons, models see",
    icon: Layers,
    color: "text-emerald-400",
    dot: "bg-emerald-400",
    children: [
      { label: "M1: RS-VQA", sub: "open / closed QA" },
      { label: "M2: Grounding", sub: "bbox + mask RLE" },
      { label: "M3: Change-VQA", sub: "categories + text" },
      { label: "M4: SAR fusion", sub: "class_map + conf" },
    ],
  },
  {
    id: "output",
    title: "OUTPUT",
    subtitle: "Evidence · Qwen Composer · Structured API → frontend",
    icon: Sparkles,
    color: "text-amber-400",
    dot: "bg-amber-400",
    children: [
      { label: "Evidence engine", sub: "Aggregate · confidence · EvidenceGraph" },
      { label: "LLM composer", sub: "Qwen 3.5 9B — fuse history + evidence" },
    ],
  },
];

export function WorkflowStack() {
  const { plannerDetails, gisDetails, taskRouter, globalStatus } = useExecutionStore();
  const { bboxes, lastCrop, history } = useSessionStore();

  return (
    <div className="rounded-xl border border-slate-800/60 bg-[#0D121F] overflow-hidden">
      <div className="px-3 py-2.5 border-b border-slate-800/60 flex items-center justify-between bg-[#090D14]/40">
        <span className="text-xs font-semibold tracking-[0.12em] text-slate-300 flex items-center gap-1.5">
          <GitBranch size={12} className="text-cyan-400" /> WORKFLOW STACK
        </span>
        <span className="text-[10px] font-mono text-slate-500">qwen-3.5-9b</span>
      </div>

      <div className="p-3 space-y-2">
        {layers.map((layer, idx) => {
          const isActive =
            (layer.id === "planner" && plannerDetails?.llm === "qwen-3.5-9b") ||
            (layer.id === "execution" && gisDetails?.cropApplied) ||
            (layer.id === "output" && globalStatus === "composing");
          return (
            <div key={layer.id} className={`relative rounded-xl border px-3 py-2.5 ${isActive ? "border-cyan-400/20 bg-cyan-400/5" : "border-slate-800/40 bg-slate-800/10"} `}>
              {idx < layers.length - 1 && <div className="absolute left-5 top-[42px] bottom-[-8px] w-px bg-slate-700/30" />}
              <div className="flex items-start gap-2.5">
                <span className={`mt-0.5 h-6 w-6 rounded-lg grid place-items-center border shrink-0 ${isActive ? "bg-cyan-400/10 border-cyan-400/20 text-cyan-400" : "bg-slate-800/60 border-slate-700/40 text-slate-400"}`}>
                  <layer.icon size={12} />
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`text-xs font-bold tracking-[0.08em] ${layer.color}`}>{layer.title}</span>
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${layer.dot} ${isActive ? "animate-pulse" : "opacity-60"}`} />
                    {layer.id === "planner" && <span className="text-[10px] font-mono text-cyan-400/70">Qwen 3.5 9B</span>}
                  </div>
                  <div className="text-[11px] text-slate-400 leading-snug mt-0.5">{layer.subtitle}</div>

                  {/* Live details */}
                  {layer.id === "planner" && plannerDetails?.coreference_resolved && (
                    <div className="mt-2 rounded-lg bg-[#090D14] border border-slate-700/30 px-2 py-1.5">
                      <div className="text-[10px] font-mono text-cyan-300">coreference: {plannerDetails.coreference_resolved}</div>
                      {plannerDetails.crop_target && <div className="text-[10px] font-mono text-slate-400">crop_target: [{plannerDetails.crop_target.join(", ")}]</div>}
                      {plannerDetails.goals && <div className="text-[10px] font-mono text-slate-500">goals: {plannerDetails.goals.join(" → ")}</div>}
                    </div>
                  )}
                  {layer.id === "execution" && (gisDetails || taskRouter || lastCrop) && (
                    <div className="mt-2 space-y-1">
                      {gisDetails && <div className="text-[10px] font-mono text-slate-300">GIS: {gisDetails.operation} {gisDetails.cropApplied ? "✓ cropped" : ""}</div>}
                      {taskRouter && <div className="text-[10px] font-mono text-slate-400">router: {Object.entries(taskRouter).map(([k, v]) => `${k}→${v}`).join(" · ")}</div>}
                      {lastCrop && <div className="text-[10px] font-mono text-slate-500">lastCrop: [{lastCrop.join(", ")}]</div>}
                      <div className="text-[10px] font-mono text-slate-500">spatial: {bboxes.length} bboxes · {history.length} turns</div>
                    </div>
                  )}

                  {layer.children && (
                    <div className="mt-2 grid grid-cols-1 gap-1">
                      {layer.children.map((c) => (
                        <div key={c.label} className="flex items-center justify-between rounded-lg bg-[#090D14] border border-slate-700/20 px-2 py-1">
                          <span className="text-[11px] font-medium text-slate-300">{c.label}</span>
                          <span className="text-[10px] font-mono text-slate-500">{c.sub}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="px-3 py-2 border-t border-slate-800/60 bg-[#090D14]/30 text-[11px] text-slate-500 leading-relaxed">
        <span className="text-slate-300 font-medium">Multi-turn:</span> Qwen resolves coreference → GIS crops ROI → Grounding runs <span className="text-emerald-400">stateless</span> on tile → Composer fuses history. Models stay blind; LLMs reason.
      </div>
    </div>
  );
}
