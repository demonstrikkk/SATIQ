// import { useRef, useState } from "react";
// import { ArrowUp, Paperclip, MapPin, X, Image as ImageIcon } from "lucide-react";
// import { useChatStore } from "@/store/chat.store";
// import { useWorkspaceStore } from "@/store/workspace.store";
// import { simulateAnalysisQuery } from "@/mocks/mockStream";
// import { analyses } from "@/mocks/analyses";
// import { cn } from "@/lib/utils";

// const CAPABILITY_HINTS = [
//   "Detect change between 2018 and 2023",
//   "Ground the largest water body",
//   "Fuse optical + SAR for this wetland",
//   "Classify land cover and count built-up",
// ];

// export function Composer({ autoFocus = false }: { autoFocus?: boolean }) {
//   const [text, setText] = useState("");
//   const [focused, setFocused] = useState(false);
//   const [dragOver, setDragOver] = useState(false);
//   const fileRef = useRef<HTMLInputElement>(null);
//   const taRef = useRef<HTMLTextAreaElement>(null);
//   const { activeContexts, addContext, removeContext, addMessage } = useChatStore();
//   const { activeAnalysisId } = useWorkspaceStore();
//   const active = analyses.find((a) => a.id === activeAnalysisId);

//   const resize = () => {
//     const t = taRef.current;
//     if (!t) return;
//     t.style.height = "auto";
//     const max = 6 * 24; // ~6 lines
//     t.style.height = Math.min(max, t.scrollHeight) + "px";
//   };

//   const send = (override?: string) => {
//     const q = (override ?? text).trim();
//     if (!q && activeContexts.length === 0) return;
//     addMessage({ id: Date.now().toString(), role: "user", content: q || "Analyze the attached imagery." });
//     simulateAnalysisQuery(q || "Analyze the attached imagery.", activeContexts);
//     setText("");
//     if (taRef.current) taRef.current.style.height = "auto";
//   };

//   const onFiles = (files: FileList | null) => {
//     if (!files) return;
//     Array.from(files).slice(0, 3).forEach((f) => addContext({ id: `file_${f.name}`, type: "image", label: f.name }));
//     if (fileRef.current) fileRef.current.value = "";
//   };

//   const addAoi = () => {
//     const label = active ? `AOI · ${active.title}` : "AOI · active region";
//     const id = `aoi_${active?.id ?? "active"}`;
//     if (!activeContexts.find((c) => c.id === id)) addContext({ id, type: "aoi", label });
//   };

//   const canSend = text.trim().length > 0 || activeContexts.length > 0;

//   return (
//     <div className="w-full">
//       <div
//         className={cn(
//           "rounded-[14px] border bg-[#0D121F] flex flex-col transition-colors",
//           focused ? "border-[#06B6D4]" : "border-slate-800/60",
//           dragOver && "border-[#06B6D4] bg-slate-800/30"
//         )}
//         onDragOver={(e: React.DragEvent) => { e.preventDefault(); setDragOver(true); }}
//         onDragLeave={() => setDragOver(false)}
//         onDrop={(e: React.DragEvent) => { e.preventDefault(); setDragOver(false); onFiles(e.dataTransfer.files); }}
//         style={{ minHeight: 64 }}
//       >
//         {activeContexts.length > 0 && (
//           <div className="flex flex-wrap gap-1.5 px-3 pt-3 pb-1">
//             {activeContexts.map((c) => (
//               <span key={c.id} className="inline-flex items-center gap-1.5 max-w-[180px] rounded-full border border-slate-800/60 bg-[#090D14] px-2.5 py-1 text-xs text-slate-400">
//                 {c.type === "aoi" ? <MapPin size={11} className="shrink-0" /> : <ImageIcon size={11} className="shrink-0" />} <span className="truncate max-w-[180px] inline-block align-middle">{c.label}</span>
//                 <button onClick={() => removeContext(c.id)} className="hover:text-white ml-0.5 shrink-0" aria-label={`Remove ${c.label}`}>
//                   <X size={11} />
//                 </button>
//               </span>
//             ))}
//           </div>
//         )}

//         <div className="flex items-end gap-2 px-3 py-3">
//           <div className="flex items-center gap-1 shrink-0">
//             <input ref={fileRef} type="file" accept=".tif,.tiff,.png,.jpg,.jpeg,.jp2" multiple hidden onChange={(e) => onFiles(e.target.files)} />
//             <button onClick={() => fileRef.current?.click()} className="h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors" aria-label="Attach">
//               <Paperclip size={16} />
//             </button>
//             <button onClick={addAoi} className="h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors" aria-label="AOI">
//               <MapPin size={16} />
//             </button>
//           </div>

//           <textarea
//             ref={taRef}
//             autoFocus={autoFocus}
//             value={text}
//             onChange={(e) => { setText(e.target.value); resize(); }}
//             onFocus={() => setFocused(true)}
//             onBlur={() => setFocused(false)}
//             onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
//             rows={1}
//             placeholder="Ask about the imagery or attach files…"
//             aria-label="Message Satiq"
//             className="flex-1 bg-transparent text-[14px] leading-relaxed text-[#F8FAFC] placeholder:text-[#64748B] outline-none resize-none py-2 max-h-[144px] min-h-[24px]"
//           />

//           <div className="flex items-center gap-2 shrink-0">
//             <span className="hidden lg:block text-[11px] text-[#64748B]">⌘K · Shift+Enter</span>
//             <button
//               onClick={() => send()}
//               disabled={!canSend}
//               className={cn(
//                 "h-8 w-8 rounded-full grid place-items-center transition-colors",
//                 canSend ? "bg-[#06B6D4] text-white hover:bg-[#0891b2] shadow-sm" : "bg-slate-800/60 text-slate-500 cursor-not-allowed"
//               )}
//               aria-label="Send"
//             >
//               <ArrowUp size={16} />
//             </button>
//           </div>
//         </div>
//       </div>

//       {focused && (
//         <div className="mt-2 flex flex-wrap gap-1.5">
//           {CAPABILITY_HINTS.map((h) => (
//             <button key={h} onClick={() => send(h)} className="rounded-full border border-slate-800/60 bg-[#0D121F] px-3 py-1 text-xs text-slate-400 hover:text-white hover:border-slate-700 hover:bg-slate-800/60 transition-colors">
//               {h}
//             </button>
//           ))}
//         </div>
//       )}
//     </div>
//   );
// }


import React, {
  useRef,
  useState,
  useCallback,
  useMemo,
  useEffect,
  useLayoutEffect,
  forwardRef,
  useImperativeHandle,
} from "react";
import {
  ArrowUp,
  Paperclip,
  MapPin,
  X,
  Image as ImageIcon,
  Loader2,
  AlertCircle,
  Clock3,
} from "lucide-react";
import { useChatStore, type ChatContext } from "@/store/chat.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useExecutionStore } from "@/store/execution.store";
import { simulateAnalysisQuery } from "@/mocks/mockStream";
import { executeRealAnalysis } from "@/lib/analysisClient";
import { analyses } from "@/mocks/analyses";
import { cn } from "@/lib/utils";

// ----------------------------------------------------------------------------
// Types & Constants
// ----------------------------------------------------------------------------

type ComposerProps = {
  autoFocus?: boolean;
  placeholder?: string;
  maxAttachments?: number;
  maxFileSizeMB?: number;
  acceptedFileTypes?: string[];
  onSend?: (message: string, contexts: ChatContext[]) => void;
  hints?: string[];
  className?: string;
};

type Context = ChatContext & {
  file?: File;
  preview?: string;
};

const SPEC_HINTS = [
  "What is visible in this image?",
  "Find the water body in the north",
  "Locate agricultural fields",
  "What changed between these dates?",
  "Show where built-up area increased",
  "Compare the optical and SAR imagery",
];
const DEFAULT_HINTS = SPEC_HINTS;

const MAX_HEIGHT = 144; // px (~6 lines)
const MIN_HEIGHT = 36;

// ----------------------------------------------------------------------------
// Sub-components
// ----------------------------------------------------------------------------

/** Renders a single context chip with remove button — shows image preview if available */
const ContextChip = React.memo(
  ({ context, onRemove }: { context: Context; onRemove: (id: string) => void }) => (
    <span className="inline-flex items-center gap-1.5 max-w-[200px] rounded-full border border-slate-800/60 bg-[#090D14] px-2.5 py-1 text-xs text-slate-400 transition-all hover:border-slate-600">
      {context.preview ? (
        <img src={context.preview} alt={context.label} className="h-5 w-5 rounded-full object-cover shrink-0 border border-slate-700" />
      ) : context.type === "aoi" ? (
        <MapPin size={11} className="shrink-0" />
      ) : (
        <ImageIcon size={11} className="shrink-0" />
      )}
      <span className="truncate max-w-[140px] inline-block align-middle">{context.label}</span>
      <button
        onClick={() => onRemove(context.id)}
        className="ml-0.5 shrink-0 rounded-full p-0.5 hover:bg-slate-700/50 hover:text-white transition-colors"
        aria-label={`Remove ${context.label}`}
      >
        <X size={11} />
      </button>
    </span>
  )
);
ContextChip.displayName = "ContextChip";

/** Renders a hint button — use onMouseDown to fire before textarea blur hides hints */
const HintButton = React.memo(
  ({ hint, onClick }: { hint: string; onClick: (h: string) => void }) => (
    <button
      onMouseDown={(e) => {
        e.preventDefault();
        onClick(hint);
      }}
      className="shrink-0 rounded-full border border-slate-800/60 bg-[#0D121F] px-3 py-1 text-xs text-slate-400 hover:text-white hover:border-slate-700 hover:bg-slate-800/60 transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none"
    >
      {hint}
    </button>
  )
);
HintButton.displayName = "HintButton";

// ----------------------------------------------------------------------------
// Main Component
// ----------------------------------------------------------------------------

export const Composer = forwardRef<{ send: (override?: string) => void }, ComposerProps>(
  (
    {
      autoFocus = false,
      placeholder = "Ask anything about the selected imagery or region...",
      maxAttachments = 5,
      maxFileSizeMB = 20,
      acceptedFileTypes = [".tif", ".tiff", ".png", ".jpg", ".jpeg", ".jp2"],
      onSend,
      hints = DEFAULT_HINTS,
      className,
    },
    ref
  ) => {
    // -------- State --------
    const [text, setText] = useState("");
    const [focused, setFocused] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [isSending, setIsSending] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // -------- Refs --------
    const fileRef = useRef<HTMLInputElement>(null);
    const taRef = useRef<HTMLTextAreaElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // -------- External Store --------
    const { activeContexts, addContext, removeContext, addMessage, queuedMessages, enqueue, dequeue, removeQueued, clearContexts } = useChatStore();
    const { globalStatus } = useExecutionStore();
    const { activeAnalysisId } = useWorkspaceStore();
    const active = useMemo(
      () => analyses.find((a) => a.id === activeAnalysisId),
      [activeAnalysisId]
    );
    const isBusy = useMemo(() => ["queued","planning","executing","aggregating","composing"].includes(globalStatus), [globalStatus]);

    // -------- Imperative handle (expose send) --------
    useImperativeHandle(
      ref,
      () => ({
        send: (override?: string) => handleSend(override),
      }),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [text, activeContexts]
    );

    // -------- Auto-resize textarea (using useLayoutEffect for sync) --------
    const resizeTextarea = useCallback(() => {
      const t = taRef.current;
      if (!t) return;
      t.style.height = "auto";
      const newHeight = Math.min(MAX_HEIGHT, t.scrollHeight);
      t.style.height = `${Math.max(MIN_HEIGHT, newHeight)}px`;
    }, []);

    useLayoutEffect(() => {
      resizeTextarea();
    }, [text, resizeTextarea]);

    useEffect(() => {
      if (autoFocus) {
        taRef.current?.focus();
      }
    }, [autoFocus]);

    // -------- File handling --------
    const processFiles = useCallback(
      (files: FileList | null) => {
        if (!files) return;
        const allowed = Array.from(files).filter(
          (f) =>
            acceptedFileTypes.some((ext) => f.name.toLowerCase().endsWith(ext)) &&
            f.size <= maxFileSizeMB * 1024 * 1024
        );

        if (allowed.length === 0) {
          setError(`No valid files. Max size: ${maxFileSizeMB}MB, types: ${acceptedFileTypes.join(", ")}`);
          return;
        }

        const toAdd = allowed.slice(0, maxAttachments - activeContexts.filter(c => c.type === "image").length);
        if (toAdd.length === 0) {
          setError("Maximum attachments reached.");
          return;
        }

        toAdd.forEach((f) => {
          const id = `file_${Date.now()}_${f.name}`;
          // Optional: generate preview for images
          let preview: string | undefined;
          if (f.type.startsWith("image/")) {
            preview = URL.createObjectURL(f);
          }
          addContext({
            id,
            type: "image",
            label: f.name,
            file: f,
            preview,
          } as Context);
        });

        if (fileRef.current) fileRef.current.value = "";
        setError(null);
      },
      [activeContexts, acceptedFileTypes, maxAttachments, maxFileSizeMB, addContext]
    );

    // -------- AOI attachment --------
    const addAoi = useCallback(() => {
      const label = active ? `AOI · ${active.title}` : "AOI · active region";
      const id = `aoi_${active?.id ?? "active"}`;
      if (!activeContexts.find((c) => c.id === id)) {
        addContext({ id, type: "aoi", label } as Context);
      }
    }, [active, activeContexts, addContext]);

    // -------- Send logic — queues if response still streaming, proxies to gateway→orchestrator else fallback to mock --------
    const handleSend = useCallback(
      async (override?: string) => {
        const q = (override ?? text).trim();
        const hasContent = q.length > 0 || activeContexts.length > 0;
        if (!hasContent) return;

        const finalMessage = q || "Analyze the attached imagery.";
        const snapshot = [...activeContexts] as ChatContext[];

        if (isBusy) {
          if (queuedMessages.length >= 5) {
            setError("Queue full (5 max) — wait for current response or delete queued items.");
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
        if (onSend) onSend(finalMessage, snapshot);
        addMessage({ id: Date.now().toString(), role: "user", content: finalMessage, contexts: snapshot });
        setText("");
        if (taRef.current) taRef.current.style.height = "auto";
        clearContexts();
        try {
          await executeRealAnalysis(finalMessage, snapshot as any);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          console.error("[analysis] gateway/orchestrator offline:", msg);
          // Show explicit offline error — do NOT silently fall back to mock (per spec: mock only when ANALYSIS_PROVIDER=mock)
          // The agentic provider already emitted an error event via applyExecutionEvent; just surface banner
          setError(`Backend offline — agentic pipeline unreachable. ${msg.slice(0,120)}`);
          // Optional: if developer explicitly wants mock fallback, set VITE_USE_MOCK=true
          if ((import.meta as any).env?.VITE_USE_MOCK === "true") {
            console.warn("[analysis] VITE_USE_MOCK=true — falling back to mock");
            await simulateAnalysisQuery(finalMessage, snapshot as any);
          }
        } finally {
          setIsSending(false);
        }
      },
      [text, activeContexts, isBusy, queuedMessages.length, enqueue, clearContexts, onSend, addMessage]
    );

    // Auto-dequeue — combine all queued into ONE complete input
    useEffect(() => {
      if ((globalStatus === "idle" || globalStatus === "completed" || globalStatus === "failed") && queuedMessages.length > 0) {
        const all = [...queuedMessages];
        const combinedContent = all.map((q) => q.content).join("\n\n");
        const combinedContexts = Array.from(new Map(all.flatMap((q) => q.contexts).map((c) => [c.id, c] as const)).values());
        useChatStore.getState().clearQueue();
        setTimeout(async () => {
          addMessage({ id: Date.now().toString(), role: "user", content: combinedContent, contexts: combinedContexts });
          try {
            await executeRealAnalysis(combinedContent, combinedContexts as any);
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            (useChatStore.getState() as any).setError?.(msg);
            console.error("[analysis] queued gateway offline:", msg);
            if ((import.meta as any).env?.VITE_USE_MOCK === "true") {
              await simulateAnalysisQuery(combinedContent, combinedContexts as any);
            }
          }
        }, 250);
      }
    }, [globalStatus, queuedMessages.length, addMessage]);

    // -------- Event handlers --------
    const onKeyDown = useCallback(
      (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
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
      (e: React.ChangeEvent<HTMLInputElement>) => {
        processFiles(e.target.files);
      },
      [processFiles]
    );

    // Clear error after 5s
    useEffect(() => {
      if (error) {
        const timer = setTimeout(() => setError(null), 5000);
        return () => clearTimeout(timer);
      }
    }, [error]);

    // -------- Derived --------
    const canSend = useMemo(
      () => text.trim().length > 0 || activeContexts.length > 0,
      [text, activeContexts]
    );

    // -------- Render --------
    return (
      <div className={cn("w-full", className)} ref={containerRef}>
        <div
          className={cn(
            "rounded-[14px] border bg-[#0D121F] flex flex-col transition-all duration-200 will-change-transform",
            focused
              ? "border-[#06B6D4] shadow-[0_0_0_2px_rgba(6,182,212,0.35)] scale-[1.015]"
              : "border-slate-800/60 scale-100",
            dragOver && "border-[#06B6D4] bg-slate-800/30 shadow-[0_0_0_2px_rgba(6,182,212,0.45)]",
            isSending && "opacity-70 pointer-events-none"
          )}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
          style={{ minHeight: focused ? 60 : 56 }}
        >
          {/* Active context — spec: subtle, auto-sent (Haryana/Sentinel-2 or Comparing) */}
          <div className="px-2.5 pt-2.5 flex items-center gap-2">
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

          {/* Context chips */}
          {activeContexts.length > 0 && (
            <div className="flex flex-wrap gap-1.5 px-2.5 pt-1 pb-1" role="list">
              {activeContexts.map((c) => (
                <ContextChip key={c.id} context={c} onRemove={removeContext} />
              ))}
            </div>
          )}

          {/* Queued messages — deletable before sent */}
          {queuedMessages.length > 0 && (
            <div className="mx-2.5 mt-1 rounded-lg border border-amber-500/20 bg-amber-500/[0.07] px-2.5 py-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold tracking-wide text-amber-300/90">QUEUED • {queuedMessages.length}/5 — will send after current response</span>
                <button onClick={() => (useChatStore.getState().clearQueue())} className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors">Clear all</button>
              </div>
              <div className="space-y-1.5">
                {queuedMessages.map((q, idx) => (
                  <div key={q.id} className="flex items-center gap-2 rounded-lg bg-[#090D14] border border-slate-800/60 px-2.5 py-2 group">
                    <span className="text-[11px] font-mono text-slate-500 shrink-0">#{idx + 1}</span>
                    <span className="flex-1 truncate text-xs text-slate-300" title={q.content}>{q.content}</span>
                    {q.contexts.length > 0 && <span className="hidden sm:inline text-[11px] text-slate-500 shrink-0">+{q.contexts.length} ctx</span>}
                    <button onClick={() => removeQueued(q.id)} className="h-6 w-6 shrink-0 grid place-items-center rounded-full text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 transition-colors" aria-label={`Remove queued: ${q.content.slice(0,30)}`}>
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Input row — items-center so icons + textarea + button share baseline */}
          <div className="flex items-center gap-2 px-2.5 py-2">
            {/* Attachment buttons */}
            <div className="flex items-center gap-1 shrink-0">
              <input
                ref={fileRef}
                type="file"
                accept={acceptedFileTypes.join(",")}
                multiple
                hidden
                onChange={onFileInputChange}
                aria-label="Attach files"
              />
              <button
                onClick={() => fileRef.current?.click()}
                className="h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none"
                aria-label="Attach files"
                disabled={isSending}
              >
                <Paperclip size={16} />
              </button>
              <button
                onClick={addAoi}
                className="h-8 w-8 grid place-items-center rounded-lg text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors focus-visible:ring-2 focus-visible:ring-cyan-400 focus-visible:outline-none"
                aria-label="Add AOI"
                disabled={isSending}
              >
                <MapPin size={16} />
              </button>
            </div>

            {/* Textarea — chrome-free, only outer container glows */}
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
              placeholder={isBusy ? "Follow-up will be queued — type and hit enter" : placeholder}
              aria-label="Message"
              disabled={isSending}
              className="composer-input flex-1 self-center bg-transparent text-[14px] leading-6 text-[#F8FAFC] placeholder:text-[#64748B] !outline-none focus:!outline-none focus-visible:!outline-none focus:ring-0 focus-visible:ring-0 focus:border-transparent focus-visible:border-transparent focus:shadow-none focus-visible:shadow-none ring-0 shadow-none border-0 resize-none py-1.5 max-h-[144px] min-h-[36px] overflow-y-auto"
            />

            {/* Send & metadata */}
            <div className="flex items-center gap-2 shrink-0">
              <span className="hidden lg:block text-[11px] text-[#64748B] select-none">
                ⌘K · Shift+Enter
              </span>
              <button
                onClick={() => handleSend()}
                disabled={!canSend}
                className={cn(
                  "h-8 w-8 rounded-full grid place-items-center transition-all relative",
                  canSend
                    ? isBusy
                      ? "bg-amber-500 text-white hover:bg-amber-600 shadow-sm hover:shadow-md active:scale-95"
                      : "bg-[#06B6D4] text-white hover:bg-[#0891b2] shadow-sm hover:shadow-md active:scale-95"
                    : "bg-slate-800/60 text-slate-500 cursor-not-allowed"
                )}
                aria-label={isBusy ? "Queue message" : "Send"}
                title={isBusy ? "Response in progress — will be queued" : "Send"}
              >
                {isSending ? <Loader2 size={16} className="animate-spin" /> : isBusy && canSend ? <Clock3 size={14} /> : <ArrowUp size={16} />}
              </button>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-400">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}

        {/* Hint buttons (only when focused and not sending) — wrap gracefully, scroll horizontally on small screens */}
        {focused && !isSending && (
          <div className="mt-2 flex gap-1.5 overflow-x-auto no-scrollbar flex-nowrap md:flex-wrap md:overflow-visible pb-1" role="toolbar" aria-label="Suggested queries">
            {hints.map((h) => (
              <HintButton key={h} hint={h} onClick={handleSend} />
            ))}
          </div>
        )}
      </div>
    );
  }
);

Composer.displayName = "Composer";

// Default export for convenience
export default Composer;