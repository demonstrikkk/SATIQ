import { Menu, Sparkles, Zap, Brain, ChevronDown } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";

type ModelMode = "Auto" | "Fast" | "Thinking";
const MODES: { id: ModelMode; label: string; desc: string; icon: any }[] = [
  { id: "Auto", label: "Auto", desc: "Best for most", icon: Sparkles },
  { id: "Fast", label: "Fast", desc: "Quick answers", icon: Zap },
  { id: "Thinking", label: "Thinking", desc: "Deep reasoning", icon: Brain },
];

export function TopCommandBar({ leftOpen, rightOpen, onToggleLeft, onToggleRight }: { leftOpen?: boolean; rightOpen?: boolean; onToggleLeft?: () => void; onToggleRight?: () => void }) {
  const [mode, setMode] = useState<ModelMode>("Auto");
  const [open, setOpen] = useState(false);
  const [modelOpen, setModelOpen] = useState(false);
  const ActiveIcon = MODES.find(m => m.id === mode)!.icon;

  return (
    <header className="h-[56px] shrink-0 flex items-center justify-between px-4 border-b border-slate-800/60 bg-[#090D14] sticky top-0 z-30">
      {/* Left: Logo + Brand */}
      <div className="flex items-center gap-3">
        <motion.button
          onClick={onToggleLeft}
            className="h-8 w-8 rounded-lg bg-[#0D121F] border border-slate-800/60 hover:bg-slate-800/60 flex items-center justify-center"
          whileTap={{ scale: 0.94 }}
          aria-label={leftOpen ? "Close sidebar" : "Open sidebar"}
        >
          <Menu size={18} className="text-slate-400" />
        </motion.button>

        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-full bg-gradient-to-br from-[#06B6D4] to-cyan-400 grid place-items-center shadow-md">
            <span className="text-white text-[11px] font-bold tracking-tighter">◎</span>
          </div>
          <div className="leading-none">
            <div className="text-[15px] font-semibold tracking-[-0.02em] text-[#F8FAFC] flex items-baseline gap-[1px]"><span>SAT</span><span className="text-[#60A5FA]">IQ</span></div>
            <div className="hidden sm:block text-[11px] text-[#64748B] tracking-wide">SEE DEEPER. REDEFINE ACCURACY.</div>
          </div>
        </div>

        {/* Model selector pill */}
        <div className="hidden md:flex relative ml-2">
          <button
            onClick={() => setModelOpen(!modelOpen)}
            className="h-8 flex items-center gap-1.5 rounded-full bg-[#0D121F] border border-slate-800/60 px-3 text-xs text-slate-200 hover:border-[#06B6D4]/30 transition-colors"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E] animate-pulse" />
            Qwen 3.5 9B · planner · composer
            <ChevronDown size={12} className={`text-slate-400 transition-transform ${modelOpen ? "rotate-180" : ""}`} />
          </button>
          <AnimatePresence>
            {modelOpen && (
              <motion.div
                initial={{ opacity: 0, y: 6, scale: 0.98 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 6, scale: 0.98 }}
                transition={{ type: "spring", stiffness: 380, damping: 28 }}
                className="absolute top-9 left-0 z-50 w-[260px] rounded-xl border border-slate-800/60 bg-[#0D121F] shadow-xl overflow-hidden"
              >
                <div className="px-3 py-2 border-b border-slate-800/60 text-xs text-slate-400">Model</div>
                <button className="w-full text-left px-3 py-2.5 flex items-center gap-2 bg-[#0D121F] text-white">
                  <span className="h-2 w-2 rounded-full bg-[#22C55E]" /> Qwen 3.5 9B <span className="ml-auto text-[11px] text-[#60A5FA]">Active</span>
                </button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Mode toggles segmented */}
        <div className="hidden lg:flex items-center rounded-full bg-[#0D121F] border border-slate-800/60 p-1 ml-2">
          {(["Fast", "Thinking"] as const).map(m => (
            <button
              key={m}
              onClick={() => setMode(m as ModelMode)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${mode === m ? "bg-[#06B6D4] text-white shadow-sm" : "text-[#94A3B8] hover:text-white"}`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Center - hidden on small */}
      <div className="hidden xl:flex items-center gap-2">
        <div className="h-8 flex items-center gap-1.5 rounded-full bg-[#0D121F] border border-slate-800/60 px-3">
          <ActiveIcon size={14} className="text-[#60A5FA]" />
          <span className="text-xs text-slate-200">{mode}</span>
          <button onClick={() => setOpen(!open)} className="ml-1">
            <ChevronDown size={12} className={`text-slate-400 transition-transform ${open ? "rotate-180" : ""}`} />
          </button>
        </div>
        <AnimatePresence>
          {open && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 6 }}
              className="absolute top-[56px] left-1/2 -translate-x-1/2 z-50 w-[220px] rounded-xl border border-slate-800/60 bg-[#0D121F] shadow-xl overflow-hidden"
            >
              {MODES.map(m => (
                <button key={m.id} onClick={() => { setMode(m.id); setOpen(false); }} className={`w-full text-left px-3 py-2.5 flex items-center gap-2 hover:bg-[#0D121F] ${mode === m.id ? "bg-[#0D121F] text-white" : "text-slate-400"}`}>
                  <m.icon size={14} className={mode === m.id ? "text-[#60A5FA]" : "text-slate-500"} />
                  <div><div className="text-xs font-medium">{m.label}</div><div className="text-[11px] text-slate-500">{m.desc}</div></div>
                </button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Right side */}
      <div className="flex items-center gap-2">
        <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-[#0D121F] border border-slate-800/60 px-2.5 py-1 text-xs text-slate-400">
          <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E] animate-pulse" /> Agentic · Online
        </span>

        <motion.button
          onClick={onToggleRight}
          whileTap={{ scale: 0.97 }}
          className={`hidden sm:flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors h-8 ${
            rightOpen ? "bg-[#06B6D4] border-[#06B6D4] text-white" : "bg-[#0D121F] border-slate-800/60 text-slate-400 hover:text-white"
          }`}
        >
          <Brain size={14} />
          <span className="hidden lg:inline">Thinking</span>
        </motion.button>

        <Button variant="ghost" size="icon" className="sm:hidden h-8 w-8 rounded-lg bg-[#0D121F] border border-slate-800/60" onClick={onToggleRight} aria-label="Toggle pipeline">
          <Brain size={16} className={rightOpen ? "text-[#06B6D4]" : "text-slate-400"} />
        </Button>

        <div className="h-7 w-7 rounded-full bg-[#0D121F] border border-slate-800/60 overflow-hidden">
          <img src="https://i.pravatar.cc/100?img=12" alt="avatar" className="h-full w-full object-cover" />
        </div>
      </div>
    </header>
  );
}
