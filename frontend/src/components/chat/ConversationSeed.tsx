import React, { useState, useRef, useCallback, useEffect, useLayoutEffect, useMemo } from "react";
import { Paperclip, ArrowUp, MapPin, X, Image as ImageIcon, Loader2, AlertCircle, Clock3 } from "lucide-react";
import { useChatStore, type ChatContext } from "@/store/chat.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useExecutionStore } from "@/store/execution.store";
import { simulateAnalysisQuery } from "@/mocks/mockStream";
import { analyses } from "@/mocks/analyses";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { motion, AnimatePresence } from "framer-motion";

// ─── Earth visual — atmospheric landing background ─────────────────────────────
function EarthHalf() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none select-none" aria-hidden>
      {/* Deep space base */}
      <div
        className="absolute inset-0"
        style={{ background: "radial-gradient(ellipse 140% 80% at 50% 100%, rgba(5,8,15,0.96) 0%, rgba(2,4,12,0.88) 35%, transparent 65%)" }}
      />

      {/* Horizon atmospheric glow */}
      <div
        className="absolute left-1/2 bottom-0 -translate-x-1/2"
        style={{
          width: "110vw",
          maxWidth: 1280,
          height: "28vh",
          bottom: "-4vh",
          background: "radial-gradient(ellipse 50% 40% at 50% 65%, rgba(6,182,212,0.07) 0%, rgba(0,100,200,0.03) 40%, transparent 72%)",
          filter: "blur(24px)",
        }}
      />

      {/* Thin atmospheric horizon line */}
      <div
        className="absolute left-1/2 bottom-0 -translate-x-1/2"
        style={{
          width: "85vw",
          maxWidth: 960,
          height: 1.5,
          bottom: "-0.5px",
          background:
            "linear-gradient(90deg, transparent 0%, rgba(6,182,212,0.25) 12%, rgba(100,200,255,0.9) 38%, rgba(220,245,255,1) 50%, rgba(100,200,255,0.9) 62%, rgba(6,182,212,0.25) 88%, transparent 100%)",
          boxShadow: "0 0 24px rgba(6,182,212,0.5), 0 0 48px rgba(0,120,255,0.2)",
        }}
      />

      {/* Earth sphere — smooth circular orbit (revolving, not spinning) — 10°/3s = 108s/orbit */}
      <div className="absolute left-1/2 bottom-20 w-[110vw] max-w-[1260px] aspect-square" style={{ animation: "earthOrbit 108s linear infinite", willChange: "transform", transform: "translate(-50%, 72%)" }}>
        <div className="relative w-full h-full rounded-full overflow-hidden" style={{ clipPath: "circle(50%)" }}>
          {/* Earth texture — static, the whole sphere orbits smoothly */}
          <div className="absolute inset-0">
            <img
              src="https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?w=1600&h=1600&fit=crop&crop=center"
              alt=""
              className="w-full h-full object-cover"
              style={{ filter: "brightness(0.95) saturate(1.05) contrast(1.02)" }}
            />
          </div>
          {/* Atmospheric limb glow */}
          <div
            className="absolute inset-0"
            style={{
              background:
                "radial-gradient(circle at 50% 50%, transparent 60%, rgba(6,182,212,0.06) 66%, rgba(6,182,212,0.18) 72%, rgba(100,200,255,0.28) 76%, rgba(0,80,200,0.08) 82%, rgba(0,0,0,0.5) 100%)",
              filter: "blur(2px)",
            }}
          />
          {/* Specular highlight */}
          <div className="absolute inset-0 overflow-hidden">
            <div
              className="absolute top-[14%] left-[22%] w-[28%] h-[18%] rounded-full"
              style={{
                background: "radial-gradient(ellipse at center, rgba(255,255,255,0.06) 0%, transparent 70%)",
                transform: "rotate(-10deg)",
              }}
            />
          </div>
          {/* Edge darkening */}
          <div
            className="absolute inset-0"
            style={{
              background: "radial-gradient(circle at 50% 50%, transparent 38%, rgba(2,4,12,0.12) 68%, rgba(2,4,12,0.28) 100%)",
            }}
          />
        </div>
      </div>

      {/* Foreground haze — blend Earth into UI */}
      <div
        className="absolute left-0 right-0 bottom-0 h-[35vh] pointer-events-none"
        style={{
          background: "linear-gradient(to top, #05080F 0%, rgba(5,8,15,0.85) 18%, rgba(5,8,15,0.18) 44%, transparent 100%)",
          zIndex: 5,
        }}
      />
    </div>
  );
}

// ─── Starfield ────────────────────────────────────────────────────────────────
function Starfield() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden>
      <div className="absolute inset-0" style={{ background: "#02040F" }} />

      {/* Nebula clouds */}
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse 800px 600px at 10% 20%, rgba(30,80,200,0.08), transparent 65%),
            radial-gradient(ellipse 700px 500px at 90% 70%, rgba(6,182,212,0.06), transparent 65%),
            radial-gradient(ellipse 1100px 800px at 50% 50%, rgba(5,8,25,0.96), transparent 75%)
          `,
        }}
      />

      {/* Dense small stars */}
      <div
        className="absolute inset-0 opacity-50"
        style={{
          backgroundImage: `
            radial-gradient(1.1px 1.1px at 7% 13%, rgba(255,255,255,0.95) 50%, transparent 50%),
            radial-gradient(1px 1px at 21% 36%, rgba(255,255,255,0.72) 50%, transparent 50%),
            radial-gradient(1.2px 1.2px at 36% 10%, rgba(255,255,255,0.88) 50%, transparent 50%),
            radial-gradient(1px 1px at 51% 26%, rgba(186,230,255,0.82) 50%, transparent 50%),
            radial-gradient(1px 1px at 67% 16%, rgba(255,255,255,0.78) 50%, transparent 50%),
            radial-gradient(1.1px 1.1px at 77% 40%, rgba(255,255,255,0.92) 50%, transparent 50%),
            radial-gradient(1px 1px at 87% 20%, rgba(186,230,255,0.72) 50%, transparent 50%),
            radial-gradient(1.3px 1.3px at 13% 60%, rgba(255,255,255,0.82) 50%, transparent 50%),
            radial-gradient(1px 1px at 27% 76%, rgba(255,255,255,0.62) 50%, transparent 50%),
            radial-gradient(1.1px 1.1px at 43% 80%, rgba(255,255,255,0.88) 50%, transparent 50%),
            radial-gradient(1px 1px at 61% 66%, rgba(186,230,255,0.78) 50%, transparent 50%),
            radial-gradient(1.2px 1.2px at 73% 86%, rgba(255,255,255,0.72) 50%, transparent 50%),
            radial-gradient(1px 1px at 91% 66%, rgba(255,255,255,0.88) 50%, transparent 50%),
            radial-gradient(1px 1px at 17% 90%, rgba(255,255,255,0.62) 50%, transparent 50%),
            radial-gradient(1px 1px at 57% 50%, rgba(255,255,255,0.52) 50%, transparent 50%),
            radial-gradient(1px 1px at 31% 46%, rgba(186,230,255,0.52) 50%, transparent 50%)
          `,
        }}
      />

      {/* Bright twinkling stars */}
      <div
        className="absolute inset-0 star-twinkle"
        style={{
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
        }}
      />

      {/* Subtle topo coordinate grid */}
      <div className="absolute inset-0 satiq-topo-grid opacity-60" />
    </div>
  );
}

// ─── Context chip ─────────────────────────────────────────────────────────────
type Context = ChatContext & {
  file?: File;
  preview?: string;
};

const ContextChip = React.memo(({ context, onRemove }: { context: Context; onRemove: (id: string) => void }) => (
  <motion.span
    initial={{ scale: 0.85, opacity: 0, y: 4 }}
    animate={{ scale: 1, opacity: 1, y: 0 }}
    exit={{ scale: 0.85, opacity: 0, y: 4 }}
    transition={{ type: "spring", stiffness: 400, damping: 22 }}
    className="inline-flex items-center gap-1.5 max-w-[200px] rounded-full border border-slate-700/50 bg-[#05080F] px-2.5 py-1 text-xs text-slate-300 backdrop-blur-sm transition-all hover:border-slate-600 hover:bg-[#101827]"
  >
    {context.preview ? (
      <img src={context.preview} alt={context.label} className="h-5 w-5 rounded-full object-cover shrink-0 border border-slate-700" />
    ) : context.type === "aoi" ? (
      <MapPin size={11} className="shrink-0 text-[#06B6D4]" />
    ) : (
      <ImageIcon size={11} className="shrink-0 text-slate-400" />
    )}
    <span className="truncate max-w-[140px] inline-block align-middle">{context.label}</span>
    <button
      onClick={() => onRemove(context.id)}
      className="ml-0.5 shrink-0 rounded-full p-0.5 hover:bg-slate-700/60 hover:text-white transition-colors"
      aria-label={`Remove ${context.label}`}
    >
      <X size={10} />
    </button>
  </motion.span>
));
ContextChip.displayName = "ContextChip";

// ─── Example query cards — ambient affordance ──────────────────────────────────
const EXAMPLE_QUERIES = [
  {
    query: "What changed between these dates?",
    meta: "Change detection · Sentinel-2",
    color: "#F59E0B",
  },
  {
    query: "Find water bodies in the north",
    meta: "Geospatial grounding · SAR",
    color: "#06B6D4",
  },
  {
    query: "Compare optical and SAR imagery",
    meta: "Fusion analysis · Multi-modal",
    color: "#8B5CF6",
  },
];

const ExampleCard = React.memo(
  ({ example, onClick }: { example: (typeof EXAMPLE_QUERIES)[0]; onClick: (q: string) => void }) => (
    <motion.button
      whileHover={{ y: -2, scale: 1.01 }}
      whileTap={{ scale: 0.98 }}
      onMouseDown={(e) => {
        e.preventDefault();
        onClick(example.query);
      }}
      className="text-left rounded-xl border border-slate-800/60 bg-[#0B1120]/70 backdrop-blur-sm px-4 py-3.5 hover:border-slate-700/60 hover:bg-[#101827]/80 transition-all duration-200 focus-visible:ring-1 focus-visible:ring-[#06B6D4] focus-visible:outline-none"
      style={{ boxShadow: "0 2px 12px rgba(0,0,0,0.3)" }}
    >
      <div className="text-[13px] font-medium text-slate-200 leading-snug">{example.query}</div>
      <div className="mt-1.5 flex items-center gap-1.5">
        <span
          className="h-1.5 w-1.5 rounded-full shrink-0"
          style={{ background: example.color, boxShadow: `0 0 6px ${example.color}` }}
        />
        <span className="text-[11px] text-slate-600 font-mono">{example.meta}</span>
      </div>
    </motion.button>
  )
);
ExampleCard.displayName = "ExampleCard";

// ─── Hint pills ────────────────────────────────────────────────────────────────
const CAPABILITY_HINTS = [
  "Locate agricultural fields",
  "Show built-up area increase",
  "Detect new construction",
  "Analyze flood risk zones",
];

const HintButton = React.memo(({ hint, onClick }: { hint: string; onClick: (h: string) => void }) => (
  <motion.button
    whileHover={{ scale: 1.02, y: -1 }}
    whileTap={{ scale: 0.96 }}
    onMouseDown={(e) => {
      e.preventDefault();
      onClick(hint);
    }}
    className="shrink-0 rounded-full border border-slate-700/50 bg-[#0B1120]/60 backdrop-blur-sm px-3 py-1.5 text-[12px] text-slate-400 hover:text-slate-200 hover:border-slate-600/60 hover:bg-[#141F30]/70 transition-all duration-200 focus-visible:ring-1 focus-visible:ring-[#06B6D4] focus-visible:outline-none"
  >
    {hint}
  </motion.button>
));
HintButton.displayName = "HintButton";

// ─── MAIN — ConversationSeed ───────────────────────────────────────────────────
export function ConversationSeed({ autoFocus = false }: { autoFocus?: boolean }) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const {
    activeContexts,
    addContext,
    removeContext,
    addMessage,
    queuedMessages,
    enqueue,
    removeQueued,
    clearContexts,
  } = useChatStore();
  const { globalStatus } = useExecutionStore();
  const isBusy = useMemo(
    () => ["queued", "planning", "executing", "aggregating", "composing"].includes(globalStatus),
    [globalStatus]
  );
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
        (f) => allowedTypes.some((ext) => f.name.toLowerCase().endsWith(ext)) && f.size <= maxSizeMB * 1024 * 1024
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
        const id = `file_${Date.now()}_${f.name}_${Math.random().toString(36).slice(2, 5)}`;
        let blobUrl: string | undefined;
        try { blobUrl = URL.createObjectURL(f); } catch {}
        addContext({ id, type: "image", label: f.name, file: f, preview: blobUrl } as Context);
        try {
          const reader = new FileReader();
          reader.onload = () => {
            const dataUrl = String(reader.result || "");
            if (dataUrl.startsWith("data:")) {
              const cur = useChatStore.getState().activeContexts.find((c) => c.id === id);
              if (cur) {
                useChatStore.getState().removeContext(id);
                useChatStore.getState().addContext({ id, type: "image", label: f.name, file: f, preview: dataUrl } as Context);
              }
            }
          };
          reader.readAsDataURL(f);
        } catch {}
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
        enqueue({
          id: Date.now().toString() + Math.random().toString(36).slice(2, 6),
          content: finalMessage,
          contexts: snapshot,
          createdAt: Date.now(),
        });
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
    if (
      (globalStatus === "idle" || globalStatus === "completed" || globalStatus === "failed") &&
      queuedMessages.length > 0
    ) {
      const all = [...queuedMessages];
      const combinedContent = all.map((q) => q.content).join("\n\n");
      const combinedContexts = Array.from(
        new Map(all.flatMap((q) => q.contexts).map((c) => [c.id, c] as const)).values()
      );
      useChatStore.getState().clearQueue();
      setTimeout(() => {
        addMessage({ id: Date.now().toString(), role: "user", content: combinedContent, contexts: combinedContexts });
        simulateAnalysisQuery(combinedContent, combinedContexts);
      }, 250);
    }
  }, [globalStatus, queuedMessages.length, addMessage]);

  const onKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSend();
        return;
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      processFiles(e.dataTransfer.files);
    },
    [processFiles]
  );

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

  return (
    <div className="relative min-h-screen flex flex-col" style={{ background: "#02040F" }}>
      <Starfield />
      <EarthHalf />

      {/* Radial vignette to focus center */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 900px 560px at 50% 38%, transparent 40%, rgba(2,4,15,0.5) 75%)",
          zIndex: 6,
        }}
      />

      {/* ── Hero content ───────────────────────────────────────────────── */}
      <div className="relative flex-1 flex flex-col items-center justify-end px-6 pb-8 bottom-24" style={{ zIndex: 10 }}>
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-[680px] flex flex-col items-center text-center mb-6"
        >
          {/* Satellite beacon — lamp + cone signal behind text/input (elegant, z-index back) */}
          <div className="relative mb-5" style={{ width: 56, height: 56 }}>
            {/* Cone beam — static soft base (more visible for debugging) */}
            <div
              aria-hidden
              className="pointer-events-none absolute left-1/2 top-[28px] -translate-x-1/2 -z-10"
              style={{
                width: "720px",
                height: "560px",
                background: "linear-gradient(180deg, rgba(6,182,212,0.18) 0%, rgba(6,182,212,0.08) 32%, rgba(6,182,212,0.03) 58%, transparent 82%)",
                clipPath: "polygon(49.35% 0%, 50.65% 0%, 84% 100%, 16% 100%)",
                filter: "blur(0.7px)",
                opacity: 0.9,
              }}
            />
            {/* Sweeping lamp beam — smooth down and back, repeats */}
            <div
              aria-hidden
              className="pointer-events-none absolute left-1/2 top-[28px] -translate-x-1/2 -z-10 overflow-hidden"
              style={{
                width: "720px",
                height: "560px",
                clipPath: "polygon(49.35% 0%, 50.65% 0%, 84% 100%, 16% 100%)",
              }}
            >
              <div
                className="absolute inset-x-0"
                style={{
                  top: "-20%",
                  height: "55%",
                  background: "linear-gradient(180deg, transparent 0%, rgba(6,182,212,0.32) 18%, rgba(6,182,212,0.20) 38%, rgba(255,255,255,0.10) 52%, transparent 78%)",
                  filter: "blur(0.5px)",
                  animation: "beamSweep 3.2s ease-in-out infinite alternate",
                  willChange: "transform",
                }}
              />
            </div>
            {/* Lamp halo behind satellite */}
            <div className="absolute inset-0 rounded-full bg-[#06B6D4]/20 blur-[18px] -z-10" style={{ transform: "scale(1.45)" }} />
            <div
              className="relative h-14 w-14 rounded-full bg-[#05080F]/90 backdrop-blur border border-white/10 grid place-items-center"
              style={{ boxShadow: "0 0 24px rgba(6,182,212,0.22), 0 0 0 1px rgba(255,255,255,0.04) inset, 0 0 18px rgba(6,182,212,0.12) inset" }}
            >
              <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden>
                {/* left panel */}
                <rect x="3.5" y="12.5" width="7.5" height="7" rx="0.7" fill="#0F1A2E" stroke="#1E3A5F" strokeWidth="0.7" />
                <line x1="4.5" y1="15" x2="10" y2="15" stroke="#1E3A5F" strokeWidth="0.4" opacity="0.6" />
                <line x1="4.5" y1="17.2" x2="10" y2="17.2" stroke="#1E3A5F" strokeWidth="0.4" opacity="0.6" />
                {/* right panel */}
                <rect x="21" y="12.5" width="7.5" height="7" rx="0.7" fill="#0F1A2E" stroke="#1E3A5F" strokeWidth="0.7" />
                <line x1="22" y1="15" x2="27.5" y2="15" stroke="#1E3A5F" strokeWidth="0.4" opacity="0.6" />
                <line x1="22" y1="17.2" x2="27.5" y2="17.2" stroke="#1E3A5F" strokeWidth="0.4" opacity="0.6" />
                {/* body */}
                <rect x="12.2" y="10.2" width="7.6" height="9.2" rx="1.2" fill="#0B1120" stroke="#06B6D4" strokeWidth="1" />
                <rect x="13.6" y="12" width="4.8" height="2.2" rx="0.6" fill="#06B6D4" opacity="0.9" />
                <circle cx="16" cy="17.2" r="1" fill="#1E3A5F" />
                {/* dish/antenna */}
                <circle cx="16" cy="7.2" r="2" fill="none" stroke="#06B6D4" strokeWidth="0.9" opacity="0.95" />
                <circle cx="16" cy="7.2" r="0.9" fill="#06B6D4" />
                <line x1="16" y1="9.2" x2="16" y2="10.2" stroke="#06B6D4" strokeWidth="0.9" />
              </svg>
              {/* lamp — nadir */}
              <span className="absolute -bottom-0.5 left-1/2 -translate-x-1/2 h-2 w-2 rounded-full bg-[#06B6D4] animate-pulse" style={{ boxShadow: "0 0 10px rgba(6,182,212,0.95), 0 0 22px rgba(6,182,212,0.55)" }} />
            </div>
          </div>

          <h1 className="text-[36px] sm:text-[44px] font-bold tracking-[-0.035em] leading-tight">
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(135deg, #F1F5F9 0%, #BAE6FD 40%, #06B6D4 80%)",
                filter: "drop-shadow(0 2px 20px rgba(0,0,0,0.9))",
              }}
            >
              Where should we look?
            </span>
          </h1>

          <p className="mt-3.5 text-[15px] leading-relaxed text-slate-500 max-w-[42ch]">
            Ask in plain language. Satiq reasons across satellite imagery,{" "}
            <span className="text-slate-400 font-medium">spatial evidence</span>, and terrain —{" "}
            every detection is auditable.
          </p>

          {/* Example query cards */}
          <div className="w-full mt-8 grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {EXAMPLE_QUERIES.map((ex) => (
              <ExampleCard key={ex.query} example={ex} onClick={handleSend} />
            ))}
          </div>
        </motion.div>

        {/* ── Composer ──────────────────────────────────────────────────── */}
        <div className="w-full max-w-[680px]">
          <div
            ref={containerRef}
            className={cn(
              "rounded-2xl transition-all duration-200 will-change-transform",
              "bg-[#0B1120]/90 backdrop-blur-xl border",
              focused
                ? "border-[#06B6D4]/60 shadow-[0_0_0_2px_rgba(6,182,212,0.2),0_16px_48px_rgba(0,0,0,0.65)] scale-[1.012]"
                : "border-slate-700/40 shadow-[0_8px_32px_rgba(0,0,0,0.55),0_1px_0_rgba(255,255,255,0.03)_inset] scale-100",
              dragOver && "border-[#06B6D4]/70 shadow-[0_0_0_2px_rgba(6,182,212,0.35)]",
              isSending && "opacity-60 pointer-events-none"
            )}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            style={{ minHeight: 56 }}
          >
            {/* Context context-line */}
            <div className="px-3.5 pt-3 flex items-center gap-2.5">
              <div className="h-6 w-6 rounded-md bg-[#05080F] border border-slate-700/40 grid place-items-center shrink-0">
                <MapPin size={10} className="text-[#06B6D4]" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-[10.5px] font-semibold tracking-[0.08em] text-slate-600 uppercase leading-none">
                  {activeContexts.find((c) => c.type === "aoi")
                    ? "AOI selected"
                    : active?.category === "change"
                    ? "Comparing"
                    : active?.category === "fusion"
                    ? "Multi-modal"
                    : "Context"}
                </div>
                <div className="text-[12px] text-slate-400 truncate leading-tight mt-0.5">
                  {activeContexts.find((c) => c.type === "aoi")?.label ??
                    (active
                      ? active.category === "change"
                        ? "2021 Scene → 2023 Scene • AOI #004"
                        : active.category === "fusion"
                        ? "Optical s2_001 + SAR s1_001 • Aligned"
                        : `${active.title} • Sentinel-2 • Aug 2026`
                      : "No region selected · Select on map or attach imagery")}
                </div>
              </div>
              <span className="hidden sm:inline text-[10.5px] text-slate-700 shrink-0 font-mono">auto-sent</span>
            </div>

            {/* Context chips */}
            <AnimatePresence>
              {activeContexts.length > 0 && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.18 }}
                  className="flex flex-wrap gap-1.5 px-3.5 pt-1.5 pb-1"
                >
                  {activeContexts.map((c) => (
                    <ContextChip key={c.id} context={c} onRemove={removeContext} />
                  ))}
                </motion.div>
              )}
            </AnimatePresence>

            {/* Queued messages */}
            {queuedMessages.length > 0 && (
              <div className="mx-3.5 mt-1.5 rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-2.5 py-2 space-y-1.5">
                <div className="flex items-center justify-between">
                  <span className="text-[10.5px] font-semibold tracking-wide text-amber-300/80">
                    QUEUED · {queuedMessages.length}/5 — will send after current response
                  </span>
                  <button
                    onClick={() => useChatStore.getState().clearQueue()}
                    className="text-[10.5px] text-slate-600 hover:text-rose-400 transition-colors"
                  >
                    Clear all
                  </button>
                </div>
                <div className="space-y-1">
                  {queuedMessages.map((q, idx) => (
                    <div
                      key={q.id}
                      className="flex items-center gap-2 rounded-lg bg-[#05080F] border border-slate-800/50 px-2.5 py-2"
                    >
                      <span className="text-[10.5px] font-mono text-slate-600 shrink-0">#{idx + 1}</span>
                      <span className="flex-1 truncate text-[12px] text-slate-300" title={q.content}>
                        {q.content}
                      </span>
                      {q.contexts.length > 0 && (
                        <span className="hidden sm:inline text-[10.5px] text-slate-600 shrink-0">
                          +{q.contexts.length} ctx
                        </span>
                      )}
                      <button
                        onClick={() => removeQueued(q.id)}
                        className="h-5 w-5 shrink-0 grid place-items-center rounded-full text-slate-600 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                        aria-label="Remove queued"
                      >
                        <X size={11} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Input row */}
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
                  className="h-8 w-8 rounded-xl text-slate-600 hover:text-slate-300 hover:bg-white/5 transition-colors"
                  onClick={() => fileRef.current?.click()}
                  aria-label="Attach files"
                  disabled={isSending}
                >
                  <Paperclip size={16} />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 rounded-xl text-slate-600 hover:text-slate-300 hover:bg-white/5 transition-colors"
                  onClick={addAoi}
                  aria-label="Add AOI"
                  disabled={isSending}
                >
                  <MapPin size={16} />
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
                placeholder={
                  isBusy
                    ? "Follow-up will be queued — type and hit enter"
                    : "Ask anything about the selected imagery or region..."
                }
                aria-label="Ask Satiq"
                disabled={isSending}
                className="composer-input flex-1 self-center bg-transparent text-[14px] leading-6 text-slate-100 placeholder:text-slate-600 !outline-none focus:!outline-none focus-visible:!outline-none focus:ring-0 focus-visible:ring-0 focus:border-transparent focus-visible:border-transparent focus:shadow-none focus-visible:shadow-none ring-0 shadow-none border-0 resize-none py-1.5 max-h-[144px] min-h-[36px] overflow-y-auto"
                style={{ height: "36px" }}
              />

              <div className="flex items-center gap-2 shrink-0">
                <span className="hidden sm:block text-[10.5px] text-slate-700 select-none font-mono">⌘K · Shift+Enter</span>
                <motion.button
                  whileHover={canSend ? { scale: 1.06 } : {}}
                  whileTap={canSend ? { scale: 0.91 } : {}}
                  onClick={() => handleSend()}
                  disabled={!canSend}
                  className={cn(
                    "h-8 w-8 rounded-full grid place-items-center transition-all duration-200",
                    canSend
                      ? isBusy
                        ? "bg-amber-500 text-white shadow-[0_3px_14px_rgba(245,158,11,0.4)] hover:bg-amber-400"
                        : "bg-gradient-to-br from-[#06B6D4] to-[#0891B2] text-white shadow-[0_3px_16px_rgba(6,182,212,0.45)] hover:shadow-[0_5px_22px_rgba(6,182,212,0.6)]"
                      : "bg-[#0B1120] text-slate-700 cursor-not-allowed"
                  )}
                  aria-label={isBusy ? "Queue message" : "Send"}
                >
                  {isSending ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : isBusy && canSend ? (
                    <Clock3 size={16} />
                  ) : (
                    <ArrowUp size={16} />
                  )}
                </motion.button>
              </div>
            </div>
          </div>

          {/* Error */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -6 }}
                className="mt-2 flex items-center gap-1.5 text-[12px] text-rose-400"
              >
                <AlertCircle size={13} />
                <span>{error}</span>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Footer disclaimer */}
          <div className="mt-3 text-center text-[10.5px] leading-relaxed text-slate-700">
            Satiq can make mistakes. Verify findings with evidence.
          </div>
        </div>
      </div>
    </div>
  );
}