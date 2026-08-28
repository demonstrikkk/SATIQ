import React, { useState, useRef, useCallback, useEffect, useLayoutEffect, useMemo } from "react";
import { Paperclip, ArrowUp, MapPin, X, Image as ImageIcon, Loader2, AlertCircle, Shield, Search, Eye, FileCheck, Zap, Clock3 } from "lucide-react";
import { useChatStore, type ChatContext } from "@/store/chat.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useExecutionStore } from "@/store/execution.store";
import { simulateAnalysisQuery } from "@/mocks/mockStream";
import { analyses } from "@/mocks/analyses";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";


function EarthHalf() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden>
      {/* Deep space background */}
      <div className="absolute inset-0" style={{
        background: `radial-gradient(ellipse 120% 70% at 50% 100%, rgba(8,16,36,0.95) 0%, rgba(2,4,12,0.85) 40%, transparent 70%)`
      }} />

      {/* Horizon glow – background glow (optional, can be removed) */}
      <div
        className="absolute left-1/2 bottom-0 -translate-x-1/2"
        style={{
          width: "120vw",
          maxWidth: 1280,
          height: "30vh",
          bottom: "-6vh",
          background: `radial-gradient(ellipse 50% 40% at 50% 60%, rgba(0,180,255,0.08) 0%, rgba(0,120,255,0.04) 30%, transparent 70%)`,
          filter: "blur(20px)",
        }}
      />

      {/* Thin horizon line */}
      <div
        className="absolute left-1/2 bottom-0 -translate-x-1/2"
        style={{
          width: "90vw",
          maxWidth: 1000,
          height: 1.8,
          bottom: "-0.5px",
          background: "linear-gradient(90deg, transparent 0%, rgba(0,200,255,0.3) 15%, rgba(100,200,255,1) 40%, rgba(200,240,255,1) 50%, rgba(100,200,255,1) 60%, rgba(0,200,255,0.3) 85%, transparent 100%)",
          boxShadow: "0 0 20px rgba(0,180,255,0.6), 0 0 40px rgba(0,120,255,0.3)",
        }}
      />

      {/* Earth container with clip-path */}
      <div className="absolute left-1/2 bottom-0 -translate-x-1/2 translate-y-[72%] w-[115vw] max-w-[1320px] aspect-square">
        <div className="relative w-full h-full rounded-full overflow-hidden" style={{ clipPath: 'circle(50%)' }}>
          {/* Earth image */}
          <img
            src="https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?w=1600&h=1600&fit=crop&crop=center"
            alt="Earth from space"
            className="w-full h-full object-cover"
            style={{ filter: "brightness(1.05) saturate(1.1)" }}
          />

          {/* Atmospheric glow – clipped to Earth */}
          <div className="absolute inset-0" style={{
            background: `radial-gradient(circle at 50% 50%, transparent 62%, rgba(0,150,255,0.08) 68%, rgba(0,200,255,0.25) 74%, rgba(100,200,255,0.35) 78%, rgba(0,100,255,0.10) 82%, rgba(0,20,40,0.6) 100%)`,
            filter: "blur(2.5px)",
            pointerEvents: "none",
          }} />

          {/* Specular highlight */}
          <div className="absolute inset-0 overflow-hidden">
            <div className="absolute top-[15%] left-[25%] w-[30%] h-[20%] rounded-full" style={{
              background: `radial-gradient(ellipse at center, rgba(255,255,255,0.08) 0%, transparent 70%)`,
              transform: 'rotate(-12deg)',
            }} />
          </div>

          {/* Subtle overlay to blend with UI */}
          <div className="absolute inset-0" style={{
            background: `radial-gradient(circle at 50% 50%, transparent 40%, rgba(2,4,12,0.15) 70%, rgba(2,4,12,0.3) 100%)`,
          }} />
        </div>
      </div>

      {/* Foreground haze */}
      <div className="absolute left-0 right-0 bottom-0 h-[32vh] pointer-events-none" style={{
        background: `linear-gradient(to top, #02040F 0%, rgba(2,4,15,0.80) 20%, rgba(2,4,15,0.15) 46%, transparent 100%)`,
        zIndex: 5,
      }} />
    </div>
  );
}
// ============================================================================
// STARFIELD – dense, with Milky Way and twinkling stars
// ============================================================================
function Starfield() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div className="absolute inset-0 bg-[#02040F]" />

      {/* Milky Way glow – diagonal band */}
      <div className="absolute inset-0" style={{
        background: `
          radial-gradient(ellipse 800px 600px at 12% 18%, rgba(37,99,235,0.10), transparent 62%),
          radial-gradient(ellipse 700px 500px at 88% 72%, rgba(14,165,233,0.08), transparent 62%),
          radial-gradient(ellipse 1100px 700px at 50% 50%, rgba(7,14,34,0.95), transparent 72%)
        `,
        opacity: 0.9
      }} />
      {/* Milky Way streak */}
      <div className="absolute inset-0" style={{
        background: `linear-gradient(135deg, transparent 30%, rgba(120,160,255,0.03) 40%, rgba(200,220,255,0.05) 50%, rgba(120,160,255,0.03) 60%, transparent 70%)`,
        transform: 'rotate(-15deg) scale(1.5)',
        opacity: 0.6
      }} />

      {/* Star layer 1 – dense small stars */}
      <div className="absolute inset-0 opacity-[0.50]" style={{
        backgroundImage: `
          radial-gradient(1.2px 1.2px at 7% 13%, rgba(255,255,255,0.95) 50%, transparent 50%),
          radial-gradient(1px 1px at 21% 36%, rgba(255,255,255,0.72) 50%, transparent 50%),
          radial-gradient(1.3px 1.3px at 36% 10%, rgba(255,255,255,0.88) 50%, transparent 50%),
          radial-gradient(1px 1px at 51% 26%, rgba(186,230,255,0.82) 50%, transparent 50%),
          radial-gradient(1.1px 1.1px at 67% 16%, rgba(255,255,255,0.78) 50%, transparent 50%),
          radial-gradient(1.2px 1.2px at 77% 40%, rgba(255,255,255,0.92) 50%, transparent 50%),
          radial-gradient(1px 1px at 87% 20%, rgba(186,230,255,0.72) 50%, transparent 50%),
          radial-gradient(1.4px 1.4px at 13% 60%, rgba(255,255,255,0.82) 50%, transparent 50%),
          radial-gradient(1px 1px at 27% 76%, rgba(255,255,255,0.62) 50%, transparent 50%),
          radial-gradient(1.2px 1.2px at 43% 80%, rgba(255,255,255,0.88) 50%, transparent 50%),
          radial-gradient(1px 1px at 61% 66%, rgba(186,230,255,0.78) 50%, transparent 50%),
          radial-gradient(1.3px 1.3px at 73% 86%, rgba(255,255,255,0.72) 50%, transparent 50%),
          radial-gradient(1px 1px at 91% 66%, rgba(255,255,255,0.88) 50%, transparent 50%),
          radial-gradient(1px 1px at 17% 90%, rgba(255,255,255,0.62) 50%, transparent 50%),
          radial-gradient(1.1px 1.1px at 57% 50%, rgba(255,255,255,0.52) 50%, transparent 50%),
          radial-gradient(1px 1px at 31% 46%, rgba(186,230,255,0.52) 50%, transparent 50%)
        `,
      }} />

      {/* Star layer 2 – bright twinkling stars */}
      <div className="absolute inset-0 opacity-30 star-twinkle" style={{
        backgroundImage: `
          radial-gradient(1.8px 1.8px at 11% 22%, #fff 50%, transparent 50%),
          radial-gradient(1.5px 1.5px at 47% 16%, #fff 50%, transparent 50%),
          radial-gradient(2px 2px at 83% 30%, #fff 50%, transparent 50%),
          radial-gradient(1.5px 1.5px at 65% 56%, #fff 50%, transparent 50%),
          radial-gradient(1.8px 1.8px at 23% 86%, #fff 50%, transparent 50%),
          radial-gradient(1.5px 1.5px at 5% 70%, #fff 50%, transparent 50%),
          radial-gradient(2.2px 2.2px at 92% 12%, #fff 50%, transparent 50%),
          radial-gradient(1.8px 1.8px at 38% 92%, #fff 50%, transparent 50%),
          radial-gradient(2px 2px at 54% 8%, #fff 50%, transparent 50%),
          radial-gradient(1.6px 1.6px at 78% 72%, #fff 50%, transparent 50%)
        `,
      }} />

      {/* Subtle grid overlay – gives a "sensor" feel */}
      <div className="absolute inset-0 opacity-[0.012]" style={{
        backgroundImage: `linear-gradient(rgba(148,163,184,0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(148,163,184,0.2) 1px, transparent 1px)`,
        backgroundSize: '48px 48px'
      }} />

      <style>{`
        .star-twinkle {
          animation: twinkle 8s ease-in-out infinite alternate;
        }
        @keyframes twinkle {
          0% { opacity: 0.15; }
          100% { opacity: 0.40; }
        }
        @media (prefers-reduced-motion: reduce) {
          .star-twinkle { animation: none; opacity: 0.20; }
        }
      `}</style>
    </div>
  );
}
// ============================================================================
// Context Chip – unchanged
// ============================================================================
type Context = ChatContext & {
  file?: File;
  preview?: string;
};

const ContextChip = React.memo(({ context, onRemove }: { context: Context; onRemove: (id: string) => void }) => (
  <motion.span
    initial={{ scale: 0.85, opacity: 0, y: 5 }}
    animate={{ scale: 1, opacity: 1, y: 0 }}
    exit={{ scale: 0.85, opacity: 0, y: 5 }}
    transition={{ type: "spring", stiffness: 400, damping: 20 }}
    className="inline-flex items-center gap-1.5 max-w-[200px] rounded-full border border-slate-700/60 bg-[#0A0F1A] px-2.5 py-1 text-xs text-slate-300 shadow-sm backdrop-blur-sm transition-all hover:border-slate-500 hover:bg-[#111827]"
  >
    {context.preview ? (
      <img src={context.preview} alt={context.label} className="h-5 w-5 rounded-full object-cover shrink-0 border border-slate-700" />
    ) : context.type === "aoi" ? (
      <MapPin size={11} className="shrink-0 text-cyan-400" />
    ) : (
      <ImageIcon size={11} className="shrink-0 text-blue-400" />
    )}
    <span className="truncate max-w-[140px] inline-block align-middle">{context.label}</span>
    <button
      onClick={() => onRemove(context.id)}
      className="ml-0.5 shrink-0 rounded-full p-0.5 hover:bg-slate-700/70 hover:text-white transition-colors"
      aria-label={`Remove ${context.label}`}
    >
      <X size={11} />
    </button>
  </motion.span>
));
ContextChip.displayName = "ContextChip";

// ============================================================================
// Hint Button
// ============================================================================
const HintButton = React.memo(({ hint, onClick }: { hint: string; onClick: (h: string) => void }) => (
  <motion.button
    whileHover={{ scale: 1.03, y: -1 }}
    whileTap={{ scale: 0.96 }}
    onMouseDown={(e) => {
      e.preventDefault();
      onClick(hint);
    }}
    className="shrink-0 rounded-full border border-slate-700/50 bg-[#0D121F]/60 backdrop-blur-sm px-3 py-1.5 text-xs text-slate-300 hover:text-white hover:border-slate-500 hover:bg-slate-800/60 transition-all duration-200 focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none shadow-sm"
  >
    {hint}
  </motion.button>
));
HintButton.displayName = "HintButton";

// ============================================================================
// MAIN – ConversationSeed (with fixed layout so input bar is always visible)
// ============================================================================
const CAPABILITY_HINTS = [
  "What is visible in this image?",
  "Find the water body in the north",
  "Locate agricultural fields",
  "What changed between these dates?",
  "Show where built-up area increased",
  "Compare the optical and SAR imagery",
];

export function ConversationSeed({ autoFocus = false }: { autoFocus?: boolean }) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { activeContexts, addContext, removeContext, addMessage, queuedMessages, enqueue, dequeue, removeQueued, clearContexts } = useChatStore();
  const { globalStatus } = useExecutionStore();
  const isBusy = useMemo(() => ["queued","planning","executing","aggregating","composing"].includes(globalStatus), [globalStatus]);
  const { activeAnalysisId } = useWorkspaceStore();
  const active = useMemo(() => analyses.find((a) => a.id === activeAnalysisId), [activeAnalysisId]);

  const resizeTextarea = useCallback(() => {
    const t = taRef.current;
    if (!t) return;
    t.style.height = "auto";
    t.style.height = `${Math.min(144, t.scrollHeight)}px`;
  }, []);

  useLayoutEffect(() => {
    resizeTextarea();
  }, [text, resizeTextarea]);

  useEffect(() => {
    if (autoFocus) taRef.current?.focus();
  }, [autoFocus]);

  const processFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      const maxSizeMB = 20;
      const allowedTypes = [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".jp2"];
      const allowed = Array.from(files).filter(
        (f) =>
          allowedTypes.some((ext) => f.name.toLowerCase().endsWith(ext)) &&
          f.size <= maxSizeMB * 1024 * 1024
      );
      if (allowed.length === 0) {
        setError(`No valid files. Max ${maxSizeMB}MB, types: ${allowedTypes.join(", ")}`);
        return;
      }
      const maxAttachments = 5;
      const toAdd = allowed.slice(0, maxAttachments - activeContexts.filter((c) => c.type === "image").length);
      if (toAdd.length === 0) {
        setError("Maximum attachments reached.");
        return;
      }
      toAdd.forEach((f) => {
        const id = `file_${Date.now()}_${f.name}`;
        let preview: string | undefined;
        if (f.type.startsWith("image/")) preview = URL.createObjectURL(f);
        addContext({ id, type: "image", label: f.name, file: f, preview } as Context);
      });
      if (fileRef.current) fileRef.current.value = "";
      setError(null);
    },
    [activeContexts, addContext]
  );

  const addAoi = useCallback(() => {
    const label = active ? `AOI · ${active.title}` : "AOI · active region";
    const id = `aoi_${active?.id ?? "active"}`;
    if (!activeContexts.find((c) => c.id === id)) {
      addContext({ id, type: "aoi", label } as Context);
    }
  }, [active, activeContexts, addContext]);

  const handleSend = useCallback(
    (override?: string) => {
      const q = (override ?? text).trim();
      const hasContent = q.length > 0 || activeContexts.length > 0;
      if (!hasContent) return;
      const finalMessage = q || "Analyze the attached imagery.";
      const snapshot = [...activeContexts] as ChatContext[];
      if (isBusy) {
        if (queuedMessages.length >= 5) {
          setError("Queue full (5 max) — wait or delete queued items.");
          return;
        }
        enqueue({ id: Date.now().toString() + Math.random().toString(36).slice(2,6), content: finalMessage, contexts: snapshot, createdAt: Date.now() });
        setText("");
        if (taRef.current) taRef.current.style.height = "auto";
        clearContexts();
        setError(null);
        return;
      }
      setIsSending(true);
      setError(null);
      addMessage({ id: Date.now().toString(), role: "user", content: finalMessage, contexts: snapshot });
      simulateAnalysisQuery(finalMessage, snapshot);
      setText("");
      if (taRef.current) taRef.current.style.height = "auto";
      clearContexts();
      setIsSending(false);
    },
    [text, activeContexts, isBusy, queuedMessages.length, enqueue, clearContexts, addMessage]
  );

  useEffect(() => {
    if ((globalStatus === "idle" || globalStatus === "completed" || globalStatus === "failed") && queuedMessages.length > 0) {
      const all = [...queuedMessages];
      const combinedContent = all.map((q) => q.content).join("\n\n");
      const combinedContexts = Array.from(new Map(all.flatMap((q) => q.contexts).map((c) => [c.id, c] as const)).values());
      useChatStore.getState().clearQueue();
      setTimeout(() => {
        addMessage({ id: Date.now().toString(), role: "user", content: combinedContent, contexts: combinedContexts });
        simulateAnalysisQuery(combinedContent, combinedContexts);
      }, 250);
    }
  }, [globalStatus, queuedMessages.length, addMessage]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const onFileInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => processFiles(e.target.files),
    [processFiles]
  );

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  const canSend = useMemo(
    () => text.trim().length > 0 || activeContexts.length > 0,
    [text, activeContexts]
  );

  const steps = [
    { icon: Shield, label: "Securing your request", desc: "Checking where you're looking" },
    { icon: Search, label: "Understanding your question", desc: "Figuring out what you need" },
    { icon: Eye, label: "Analyzing from space", desc: "Our AI looks at the imagery" },
    { icon: FileCheck, label: "Verifying the evidence", desc: "Making sure it's really there" },
    { icon: Zap, label: "Crafting your answer", desc: "Writing a clear, evidence-based response" },
  ];

  return (
    // Main container: full viewport height, flex column, no overflow hidden to keep input bar visible
    <div className="relative min-h-screen flex flex-col bg-[#02040F]">
      <Starfield />
      <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[#02040F]/90 pointer-events-none" />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_900px_520px_at_50%_36%,transparent_42%,rgba(2,4,15,0.58)_78%)] pointer-events-none" />
      <EarthHalf />

      {/* Center content – flex-1 so it pushes the composer down */}
      <div className="relative z-10 flex-1 flex flex-col items-center justify-center px-6 py-10">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.25, 0.1, 0.25, 1] }}
          className="w-full max-w-[680px] flex flex-col items-center text-center"
        >
          <div className="h-12 w-12 rounded-full bg-[#0A0F1A]/80 backdrop-blur border border-white/10 grid place-items-center shadow-[0_0_24px_rgba(6,182,212,0.3)]">
            <span className="h-3 w-3 rounded-full bg-[#22C55E] animate-pulse shadow-[0_0_12px_rgba(34,197,94,0.9)]" />
          </div>

          <h1 className="mt-5 text-[32px] sm:text-[38px] font-bold tracking-tight">
            <span className="bg-gradient-to-r from-[#F8FAFC] via-[#93C5FD] to-[#06B6D4] bg-clip-text text-transparent drop-shadow-[0_2px_16px_rgba(0,0,0,0.8)]">
              Where should we look?
            </span>
          </h1>

          <p className="mt-3 text-[15px] leading-relaxed text-[#94A3B8] max-w-[48ch]">
            Ask in plain language. Satiq plans, crops, and grounds with{" "}
            <span className="text-[#93C5FD] font-medium">Qwen 3.5 9B</span> — every detection is auditable.
          </p>

          <div className="mt-4 flex items-center gap-2 text-[12px] text-[#64748B]">
            <span className="h-1.5 w-1.5 rounded-full bg-[#64748B]" />
            No example cards — just ask
            <span className="h-1.5 w-1.5 rounded-full bg-[#334155]" />
            Try “water body in the north”
          </div>

          {/* Demo — how image will appear in chat response (conditional, graceful) */}
          

          {/* How Satiq investigates */}
         
        </motion.div>
      </div>

      {/* ========== COMPOSER – always at bottom, no clipping ========== */}
      <div className="relative z-10 shrink-0 p-4 pb-36">
        <div
          ref={containerRef}
          className={cn(
            "mx-auto max-w-[680px] rounded-2xl transition-all duration-200 will-change-transform",
            "bg-[#0A0F1A]/80 backdrop-blur-xl border",
            focused
              ? "border-[#06B6D4] shadow-[0_0_0_2px_rgba(6,182,212,0.35),0_16px_48px_rgba(0,0,0,0.6)] scale-[1.015]"
              : "border-slate-800/60 shadow-[0_8px_32px_rgba(0,0,0,0.5),0_1px_0_rgba(255,255,255,0.04)_inset] scale-100",
            dragOver && "border-[#06B6D4] bg-slate-800/30 shadow-[0_0_0_2px_rgba(6,182,212,0.45)]",
            isSending && "opacity-60 pointer-events-none"
          )}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          style={{ minHeight: focused ? 60 : 56 }}
        >
          {/* Active context — spec subtle */}
          <div className="px-3 pt-3 flex items-center gap-2">
            <div className="h-6 w-6 rounded-md bg-[#090D14] border border-slate-800/60 grid place-items-center shrink-0">
              <MapPin size={10} className="text-[#06B6D4]" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase leading-none">
                {activeContexts.find((c) => c.type === "aoi") ? "AOI selected" : active?.category === "change" ? "Comparing" : active?.category === "fusion" ? "Multi-modal" : "Selected context"}
              </div>
              <div className="text-xs text-slate-300 truncate leading-tight mt-0.5">
                {activeContexts.find((c) => c.type === "aoi")?.label ??
                  (active
                    ? active.category === "change"
                      ? "2021 Scene → 2023 Scene • AOI #004"
                      : active.category === "fusion"
                        ? "Optical s2_001 + SAR s1_001 • Aligned"
                        : `${active.title} • Sentinel-2 • Aug 2026`
                    : "No region selected • Select on map or attach imagery")}
              </div>
            </div>
            <span className="hidden sm:inline text-[11px] text-slate-500 shrink-0">auto-sent</span>
          </div>

          <AnimatePresence>
            {activeContexts.length > 0 && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.2 }}
                className="flex flex-wrap gap-1.5 px-3 pt-1 pb-1"
              >
                {activeContexts.map((c) => (
                  <ContextChip key={c.id} context={c} onRemove={removeContext} />
                ))}
              </motion.div>
            )}
          </AnimatePresence>

          {queuedMessages.length > 0 && (
            <div className="mx-3 mt-1 rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-2.5 py-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold tracking-wide text-amber-300/90">QUEUED • {queuedMessages.length}/5 — will send after current response</span>
                <button onClick={() => useChatStore.getState().clearQueue()} className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors">Clear all</button>
              </div>
              <div className="space-y-1.5">
                {queuedMessages.map((q, idx) => (
                  <div key={q.id} className="flex items-center gap-2 rounded-lg bg-[#090D14] border border-slate-800/60 px-2.5 py-2">
                    <span className="text-[11px] font-mono text-slate-500 shrink-0">#{idx + 1}</span>
                    <span className="flex-1 truncate text-xs text-slate-300" title={q.content}>{q.content}</span>
                    {q.contexts.length > 0 && <span className="hidden sm:inline text-[11px] text-slate-500 shrink-0">+{q.contexts.length} ctx</span>}
                    <button onClick={() => removeQueued(q.id)} className="h-6 w-6 shrink-0 grid place-items-center rounded-full text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 transition-colors" aria-label="Remove queued">
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="flex items-center gap-2 px-3 py-2.5">
            <div className="flex items-center gap-1 shrink-0">
              <input
                ref={fileRef}
                type="file"
                accept=".tif,.tiff,.png,.jpg,.jpeg,.jp2"
                multiple
                hidden
                onChange={onFileInputChange}
                aria-label="Attach files"
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-xl text-[#64748B] hover:text-[#F8FAFC] hover:bg-white/5 transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400"
                onClick={() => fileRef.current?.click()}
                aria-label="Attach files"
                disabled={isSending}
              >
                <Paperclip size={17} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-9 w-9 rounded-xl text-[#64748B] hover:text-[#F8FAFC] hover:bg-white/5 transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400"
                onClick={addAoi}
                aria-label="Add AOI"
                disabled={isSending}
              >
                <MapPin size={17} />
              </Button>
            </div>

            <textarea
              ref={taRef}
              autoFocus={autoFocus}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                resizeTextarea();
              }}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              onKeyDown={onKeyDown}
              rows={1}
              placeholder={isBusy ? "Follow-up will be queued — type and hit enter" : "Ask anything about the selected imagery or region..."}
              aria-label="Ask Satiq"
              disabled={isSending}
              className="composer-input flex-1 self-center bg-transparent text-[15px] leading-6 text-[#F8FAFC] placeholder:text-[#64748B] !outline-none focus:!outline-none focus-visible:!outline-none focus:ring-0 focus-visible:ring-0 focus:border-transparent focus-visible:border-transparent focus:shadow-none focus-visible:shadow-none ring-0 shadow-none border-0 resize-none py-1.5 max-h-[144px] min-h-[36px] overflow-y-auto"
              style={{ height: "36px" }}
            />

            <div className="flex items-center gap-2 shrink-0">
              <span className="hidden sm:block text-[11px] text-[#475569] select-none font-mono">⌘K · Shift+Enter</span>
              <motion.button
                whileHover={canSend ? { scale: 1.05 } : {}}
                whileTap={canSend ? { scale: 0.92 } : {}}
                onClick={() => handleSend()}
                disabled={!canSend}
                className={cn(
                  "h-9 w-9 rounded-full grid place-items-center transition-all duration-200",
                  canSend
                    ? isBusy
                      ? "bg-amber-500 text-white shadow-[0_4px_16px_rgba(245,158,11,0.4)] hover:bg-amber-600"
                      : "bg-gradient-to-br from-[#06B6D4] to-[#0891b2] text-white shadow-[0_4px_16px_rgba(6,182,212,0.5)] hover:shadow-[0_6px_24px_rgba(6,182,212,0.7)] active:shadow-inner"
                    : "bg-[#0D121F] text-[#475569] cursor-not-allowed"
                )}
                aria-label={isBusy ? "Queue message" : "Send"}
                title={isBusy ? "Response in progress — will be queued" : "Send"}
              >
                {isSending ? <Loader2 size={17} className="animate-spin" /> : isBusy && canSend ? <Clock3 size={17} /> : <ArrowUp size={17} />}
              </motion.button>
            </div>
          </div>
        </div>

        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              className="mx-auto max-w-[680px] mt-2 flex items-center gap-1.5 text-xs text-rose-400"
            >
              <AlertCircle size={14} />
              <span>{error}</span>
            </motion.div>
          )}
        </AnimatePresence>

        {focused && !isSending && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto max-w-[680px] mt-3 flex gap-1.5 overflow-x-auto no-scrollbar flex-nowrap md:flex-wrap md:overflow-visible pb-1"
          >
            {CAPABILITY_HINTS.map((h) => (
              <HintButton key={h} hint={h} onClick={handleSend} />
            ))}
          </motion.div>
        )}

        <div className="mx-auto max-w-[680px] mt-3 text-center text-[11px] leading-relaxed text-[#475569]">
          Satiq can make mistakes. Verify with evidence · Earth horizon is live SVG · no external image
        </div>
      </div>
    </div>
  );
}