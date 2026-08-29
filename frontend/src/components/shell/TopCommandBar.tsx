import { Brain, ChevronDown, Zap, Menu } from "lucide-react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";

type ModelMode = "Fast" | "Thinking";

// SATIQ product mark — orbital observation cross-hair SVG
function SatiqMark({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="SATIQ mark"
    >
      {/* Outer ring */}
      <circle cx="14" cy="14" r="12.5" stroke="url(#satiq-ring)" strokeWidth="1.25" />
      {/* Inner arc — partial, creates orbital feel */}
      <path
        d="M 14 4 A 10 10 0 0 1 24 14"
        stroke="#06B6D4"
        strokeWidth="1.5"
        strokeLinecap="round"
        opacity="0.9"
      />
      {/* Cross-hair — thin precision lines */}
      <line x1="14" y1="2" x2="14" y2="8" stroke="#06B6D4" strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
      <line x1="14" y1="20" x2="14" y2="26" stroke="#06B6D4" strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
      <line x1="2" y1="14" x2="8" y2="14" stroke="#06B6D4" strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
      <line x1="20" y1="14" x2="26" y2="14" stroke="#06B6D4" strokeWidth="1.2" strokeLinecap="round" opacity="0.5" />
      {/* Center dot */}
      <circle cx="14" cy="14" r="2.5" fill="#06B6D4" />
      {/* Gradient def */}
      <defs>
        <linearGradient id="satiq-ring" x1="0" y1="0" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#06B6D4" stopOpacity="0.6" />
          <stop offset="50%" stopColor="#0891B2" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#06B6D4" stopOpacity="0.1" />
        </linearGradient>
      </defs>
    </svg>
  );
}

// User avatar — deterministic geometric avatar, no external image
function UserAvatar({ size = 28 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-label="User"
    >
      <circle cx="14" cy="14" r="14" fill="#101827" />
      <circle cx="14" cy="11" r="4.5" fill="#1A2740" />
      <path d="M4 26c0-5.5 4.5-9 10-9s10 3.5 10 9" fill="#1A2740" />
      <circle cx="14" cy="14" r="14" stroke="rgba(51,65,85,0.55)" strokeWidth="1" />
    </svg>
  );
}

export function TopCommandBar({
  leftOpen,
  rightOpen,
  onToggleLeft,
  onToggleRight,
}: {
  leftOpen?: boolean;
  rightOpen?: boolean;
  onToggleLeft?: () => void;
  onToggleRight?: () => void;
}) {
  const [mode, setMode] = useState<ModelMode>("Thinking");
  const [modelOpen, setModelOpen] = useState(false);

  return (
    <header className="h-[56px] shrink-0 flex items-center justify-between px-3 border-b border-slate-800/50 bg-[#05080F] sticky top-0 z-30">
      {/* ── Left: hamburger + logo + model ──────────────────────────── */}
      <div className="flex items-center gap-2.5">
        <motion.button
          onClick={onToggleLeft}
          className="h-8 w-8 rounded-lg bg-[#0B1120] border border-slate-700/40 hover:bg-[#141F30] flex items-center justify-center transition-colors"
          whileTap={{ scale: 0.93 }}
          aria-label={leftOpen ? "Close sidebar" : "Open sidebar"}
        >
          <Menu size={16} className="text-slate-400" />
        </motion.button>

        {/* Brand */}
        <div className="flex items-center gap-2">
          <SatiqMark size={26} />
          <div className="leading-none select-none">
            <div className="text-[14px] font-semibold tracking-[-0.02em] text-slate-100 flex items-baseline">
              <span>SAT</span>
              <span className="text-[#06B6D4]">IQ</span>
            </div>
            <div className="hidden sm:block text-[10px] text-slate-600 tracking-[0.06em] uppercase leading-none mt-0.5">
              Spatial Intelligence
            </div>
          </div>
        </div>

        {/* Model selector */}
        <div className="hidden md:flex relative ml-1">
          <button
            onClick={() => setModelOpen(!modelOpen)}
            className="h-7 flex items-center gap-1.5 rounded-full bg-[#0B1120] border border-slate-700/40 px-2.5 text-[12px] text-slate-300 hover:border-slate-600/50 hover:bg-[#141F30] transition-colors"
          >
            <span className="h-1.5 w-1.5 rounded-full bg-[#22C55E] shrink-0" style={{ boxShadow: "0 0 6px #22C55E" }} />
            <span>Qwen 3.5 9B</span>
            <span className="text-slate-600">·</span>
            <span className="text-slate-500">planner · composer</span>
            <ChevronDown
              size={11}
              className={`text-slate-500 transition-transform duration-200 ${modelOpen ? "rotate-180" : ""}`}
            />
          </button>
          <AnimatePresence>
            {modelOpen && (
              <motion.div
                initial={{ opacity: 0, y: 5, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 5, scale: 0.97 }}
                transition={{ type: "spring", stiffness: 400, damping: 30 }}
                className="absolute top-9 left-0 z-50 w-[240px] rounded-xl border border-slate-700/40 bg-[#0B1120] shadow-[0_12px_40px_rgba(0,0,0,0.6)] overflow-hidden"
              >
                <div className="px-3 py-2 border-b border-slate-800/60">
                  <span className="text-[10px] font-semibold tracking-[0.08em] uppercase text-slate-500">Active Model</span>
                </div>
                <div className="p-1">
                  <button className="w-full text-left px-3 py-2.5 rounded-lg flex items-center gap-2.5 hover:bg-[#141F30] transition-colors">
                    <span className="h-2 w-2 rounded-full bg-[#22C55E] shrink-0" style={{ boxShadow: "0 0 6px #22C55E" }} />
                    <div>
                      <div className="text-[13px] text-white font-medium">Qwen 3.5 9B</div>
                      <div className="text-[11px] text-slate-500 font-mono">planner + composer</div>
                    </div>
                    <span className="ml-auto text-[10px] font-medium text-[#06B6D4] bg-[#06B6D4]/10 rounded-full px-2 py-0.5">Active</span>
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Mode toggle — Fast / Thinking */}
        <div className="hidden lg:flex items-center rounded-full bg-[#0B1120] border border-slate-700/40 p-0.5 ml-1">
          {(["Fast", "Thinking"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1.5 rounded-full text-[12px] font-medium transition-all duration-200 flex items-center gap-1.5 ${
                mode === m
                  ? "bg-[#06B6D4] text-white shadow-sm"
                  : "text-slate-500 hover:text-slate-200"
              }`}
            >
              {m === "Fast" ? <Zap size={11} /> : <Brain size={11} />}
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* ── Right: status + pipeline button + avatar ─────────────────── */}
      <div className="flex items-center gap-2">
        <span className="hidden sm:inline-flex items-center gap-1.5 rounded-full bg-[#0B1120] border border-slate-700/40 px-2.5 py-1 text-[11px] text-slate-400">
          <span
            className="h-1.5 w-1.5 rounded-full bg-[#22C55E]"
            style={{ boxShadow: "0 0 5px #22C55E" }}
          />
          Agentic · Online
        </span>

        <motion.button
          onClick={onToggleRight}
          whileTap={{ scale: 0.96 }}
          className={`hidden sm:flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-[12px] font-medium transition-all duration-200 h-[30px] ${
            rightOpen
              ? "bg-[#06B6D4] border-[#06B6D4] text-white shadow-[0_0_16px_rgba(6,182,212,0.3)]"
              : "bg-[#0B1120] border-slate-700/40 text-slate-400 hover:text-slate-200 hover:border-slate-600/50"
          }`}
        >
          <Brain size={13} />
          <span className="hidden lg:inline">Thinking</span>
        </motion.button>

        <Button
          variant="ghost"
          size="icon"
          className="sm:hidden h-8 w-8 rounded-lg bg-[#0B1120] border border-slate-700/40"
          onClick={onToggleRight}
          aria-label="Toggle pipeline"
        >
          <Brain size={15} className={rightOpen ? "text-[#06B6D4]" : "text-slate-400"} />
        </Button>

        <div className="h-7 w-7 rounded-full overflow-hidden border border-slate-700/50">
          <UserAvatar size={28} />
        </div>
      </div>
    </header>
  );
}
