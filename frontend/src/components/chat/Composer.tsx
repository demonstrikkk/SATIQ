import React, {
  useRef,
  useState,
  useCallback,
  useMemo,
  useEffect,
  forwardRef,
  useImperativeHandle,
} from "react";
import TextareaAutosize from "react-textarea-autosize";
import {
  ArrowUp,
  Paperclip,
  MapPin,
  X,
  Image as ImageIcon,
  Loader2,
  AlertCircle,
  Clock3,
  Square,
} from "lucide-react";
import { useChatStore, type ChatContext } from "@/store/chat.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useExecutionStore } from "@/store/execution.store";
import { simulateAnalysisQuery, cancelCurrentQuery } from "@/mocks/mockStream";
import { executeRealAnalysis } from "@/lib/analysisClient";
import { analyses } from "@/mocks/analyses";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

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

// ----------------------------------------------------------------------------
// Sub-components
// ----------------------------------------------------------------------------

const ContextChip = React.memo(
  ({ context, onRemove }: { context: Context; onRemove: (id: string) => void }) => (
    <span className="inline-flex items-center gap-1.5 max-w-[200px] rounded-full border border-slate-700/40 bg-[#05080F] px-2.5 py-1 text-xs text-slate-300 transition-all hover:border-slate-600/60">
      {context.preview ? (
        <img src={context.preview} alt={context.label} className="h-5 w-5 rounded-full object-cover shrink-0 border border-slate-700" />
      ) : context.type === "aoi" ? (
        <MapPin size={11} className="shrink-0 text-[#06B6D4]" />
      ) : (
        <ImageIcon size={11} className="shrink-0 text-slate-500" />
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

const HintButton = React.memo(
  ({ hint, onClick }: { hint: string; onClick: (h: string) => void }) => (
    <button
      onMouseDown={(e) => {
        e.preventDefault();
        onClick(hint);
      }}
      className="shrink-0 rounded-full border border-[#323a36] bg-[#121615] px-3 py-1.5 text-[12px] text-[#9aa39d] hover:text-[#06B6D4] hover:border-[rgba(6,182,212,0.35)] hover:bg-[#181d1b] transition-colors focus-visible:ring-2 focus-visible:ring-[#06B6D4]/30 focus-visible:outline-none"
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
    const [text, setText] = useState("");
    const [focused, setFocused] = useState(false);
    const [dragOver, setDragOver] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [dragRejectReason, setDragRejectReason] = useState<string | null>(null);

    const fileRef = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const { activeContexts, addContext, removeContext, addMessage, queuedMessages, enqueue, removeQueued, clearContexts } = useChatStore();
    const { globalStatus } = useExecutionStore();
    const { activeAnalysisId } = useWorkspaceStore();
    const active = useMemo(() => analyses.find((a) => a.id === activeAnalysisId), [activeAnalysisId]);
    const isBusy = useMemo(() => ["queued", "planning", "executing", "aggregating", "composing"].includes(globalStatus), [globalStatus]);

    useImperativeHandle(
      ref,
      () => ({
        send: (override?: string) => handleSend(override),
      }),
      // eslint-disable-next-line react-hooks/exhaustive-deps
      [text, activeContexts, globalStatus]
    );

    // -------- File handling --------
    const processFiles = useCallback(
      (files: FileList | null) => {
        if (!files) return;
        const existingImages = activeContexts.filter((c) => c.type === "image").length;
        const remaining = maxAttachments - existingImages;
        if (remaining <= 0) {
          const msg = `Maximum ${maxAttachments} attachments reached. Remove one to add more.`;
          setError(msg);
          toast.error(msg);
          setDragRejectReason(msg);
          setTimeout(() => setDragRejectReason(null), 2500);
          return;
        }
        const all = Array.from(files);
        const tooLarge: string[] = [];
        const badType: string[] = [];
        const valid: File[] = [];
        for (const f of all) {
          const okType = acceptedFileTypes.some((ext) => f.name.toLowerCase().endsWith(ext));
          const okSize = f.size <= maxFileSizeMB * 1024 * 1024;
          if (!okType) badType.push(f.name);
          else if (!okSize) tooLarge.push(f.name);
          else valid.push(f);
        }
        if (badType.length) {
          const msg = `Unsupported type: ${badType.slice(0, 2).join(", ")} — allowed: ${acceptedFileTypes.join(", ")}`;
          setError(msg);
          toast.error(msg);
        }
        if (tooLarge.length) {
          const msg = `${tooLarge.slice(0, 2).join(", ")} exceeds ${maxFileSizeMB}MB`;
          setError(msg);
          toast.error(msg);
        }
        const toAdd = valid.slice(0, remaining);
        if (toAdd.length === 0) {
          if (valid.length > remaining) {
            const msg = `Only ${remaining} slot(s) left — extra files ignored.`;
            toast.message(msg);
          }
          return;
        }
        // Immediate blob preview for instant UX, then upgrade to data URL for persistence (localStorage survival across reload).
        toAdd.forEach((f) => {
          const id = `file_${Date.now()}_${f.name}_${Math.random().toString(36).slice(2, 5)}`;
          let blobUrl: string | undefined;
          try {
            blobUrl = URL.createObjectURL(f);
          } catch {}
          addContext({ id, type: "image", label: f.name, file: f, preview: blobUrl } as Context);
          // Upgrade to data URL async so snapshot sent a moment later has persistable preview
          try {
            const reader = new FileReader();
            reader.onload = () => {
              const dataUrl = String(reader.result || "");
              if (dataUrl.startsWith("data:")) {
                const { activeContexts } = useChatStore.getState();
                if (activeContexts.find((c) => c.id === id)) {
                  useChatStore.getState().removeContext(id);
                  useChatStore.getState().addContext({ id, type: "image", label: f.name, file: f, preview: dataUrl } as Context);
                }
              }
            };
            reader.readAsDataURL(f);
          } catch {}
        });
        if (toAdd.length < valid.length) {
          toast.message(`Added ${toAdd.length} of ${valid.length} files — ${maxAttachments} max.`);
        } else if (toAdd.length) {
          toast.success(`Added ${toAdd.length} file(s)`);
        }
        if (fileRef.current) fileRef.current.value = "";
        setError(null);
        setDragRejectReason(null);
      },
      [activeContexts, acceptedFileTypes, maxAttachments, maxFileSizeMB, addContext]
    );

    const addAoi = useCallback(() => {
      const label = active ? `AOI · ${active.title}` : "AOI · active region";
      const id = `aoi_${active?.id ?? "active"}`;
      if (!activeContexts.find((c) => c.id === id)) {
        addContext({ id, type: "aoi", label } as Context);
        toast.success("AOI attached");
      } else {
        toast.message("AOI already attached");
      }
    }, [active, activeContexts, addContext]);

    const handleSend = useCallback(
      async (override?: string) => {
        const q = (override ?? text).trim();
        const hasContent = q.length > 0 || activeContexts.length > 0;
        if (!hasContent) return;

        const finalMessage = q || "Analyze the attached imagery.";
        const snapshot = [...activeContexts] as ChatContext[];

        if (isBusy) {
          if (queuedMessages.length >= 5) {
            const msg = "Queue full (5 max) — wait or delete queued items.";
            setError(msg);
            toast.error(msg);
            return;
          }
          enqueue({ id: Date.now().toString() + Math.random().toString(36).slice(2, 6), content: finalMessage, contexts: snapshot, createdAt: Date.now() });
          setText("");
          clearContexts();
          setError(null);
          toast.message("Queued — will send after current response");
          return;
        }

        setError(null);
        if (onSend) onSend(finalMessage, snapshot);
        addMessage({ id: Date.now().toString(), role: "user", content: finalMessage, contexts: snapshot });
        setText("");
        clearContexts();
        try {
          await executeRealAnalysis(finalMessage, snapshot as any);
        } catch (err) {
          const msg = err instanceof Error ? err.message : String(err);
          console.error("[analysis] gateway/orchestrator offline:", msg);
          setError(`Backend offline — agentic pipeline unreachable. ${msg.slice(0,120)}`);
          if ((import.meta as any).env?.VITE_USE_MOCK === "true") {
            console.warn("[analysis] VITE_USE_MOCK=true — falling back to mock");
            await simulateAnalysisQuery(finalMessage, snapshot as any);
          }
        }
      },
      [text, activeContexts, isBusy, queuedMessages.length, enqueue, clearContexts, onSend, addMessage]
    );

    // Auto-dequeue — combine all queued into ONE
    useEffect(() => {
      if ((globalStatus === "idle" || globalStatus === "completed" || globalStatus === "failed" || globalStatus === "cancelled") && queuedMessages.length > 0) {
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
            console.error("[analysis] queued gateway offline:", msg);
            if ((import.meta as any).env?.VITE_USE_MOCK === "true") {
              await simulateAnalysisQuery(combinedContent, combinedContexts as any);
            } else {
              setError(`Backend offline — ${msg.slice(0,100)}`);
            }
          }
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
        if (e.key === "Escape" && isBusy) {
          e.preventDefault();
          cancelCurrentQuery();
          toast.message("Generation stopped");
        }
      },
      [handleSend, isBusy]
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
      const hasFiles = e.dataTransfer.types.includes("Files");
      setDragOver(hasFiles);
    }, []);
    const onDragLeave = useCallback((e: React.DragEvent) => {
      e.preventDefault();
      // only clear if leaving container
      if (!containerRef.current?.contains(e.relatedTarget as Node)) setDragOver(false);
    }, []);

    const onFileInputChange = useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => processFiles(e.target.files),
      [processFiles]
    );

    useEffect(() => {
      if (error) {
        const t = setTimeout(() => setError(null), 4000);
        return () => clearTimeout(t);
      }
    }, [error]);

    const canSend = useMemo(() => text.trim().length > 0 || activeContexts.length > 0, [text, activeContexts]);

    // ---- Stop handler ----
    const handleStop = useCallback(() => {
      const ok = cancelCurrentQuery();
      if (ok) toast.message("Stopped generation");
    }, []);

    return (
      <div className={cn("w-full", className)} ref={containerRef}>

        <div
          className={cn(
            "relative rounded-[10px] border bg-[#121615] flex flex-col transition-all duration-150 will-change-transform overflow-hidden",
            focused ? "border-[rgba(6,182,212,0.35)] shadow-[0_0_0_3px_rgba(6,182,212,0.10)]" : "border-[#323a36]",
            dragOver && "border-[rgba(6,182,212,0.45)] bg-[#181d1b] shadow-[0_0_0_3px_rgba(6,182,212,0.08)]"
          )}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          {/* Drag overlay */}
          {dragOver && (
            <div className="absolute inset-0 z-10 grid place-items-center bg-[#0b0f0d]/80 backdrop-blur-[2px] border-2 border-dashed border-[#06B6D4]/50 rounded-[10px] pointer-events-none">
              <div className="flex flex-col items-center gap-2 text-center">
                <div className="h-10 w-10 rounded-full bg-[#06B6D4]/15 border border-[#06B6D4]/30 grid place-items-center">
                  <Paperclip size={18} className="text-[#06B6D4]" />
                </div>
                <div className="text-sm font-medium text-[#e9ece9]">Drop imagery to attach</div>
                <div className="text-xs text-[#9aa39d]">{acceptedFileTypes.join(" · ")} · {maxFileSizeMB}MB max</div>
                {dragRejectReason && <div className="text-xs text-amber-400 mt-1">{dragRejectReason}</div>}
              </div>
            </div>
          )}

          {/* Active context header */}
          <div className="px-2.5 pt-2.5 flex items-center gap-2">
            <div className="h-6 w-6 rounded-md bg-[#05080F] border border-slate-700/40 grid place-items-center shrink-0">
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
            <div className="flex flex-wrap gap-1.5 px-2.5 pt-2 pb-1" role="list" aria-label="Attached contexts">
              {activeContexts.map((c) => (
                <ContextChip key={c.id} context={c} onRemove={removeContext} />
              ))}
            </div>
          )}

          {/* Queued messages */}
          {queuedMessages.length > 0 && (
            <div className="mx-2.5 mt-1 rounded-xl border border-amber-500/20 bg-amber-500/[0.06] px-2.5 py-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-semibold tracking-wide text-amber-300/90">QUEUED • {queuedMessages.length}/5 — will send after current response</span>
                <button
                  onClick={() => useChatStore.getState().clearQueue()}
                  className="text-[11px] text-slate-500 hover:text-rose-400 transition-colors rounded px-1.5 py-0.5 hover:bg-amber-500/10"
                >
                  Clear all
                </button>
              </div>
              <div className="space-y-1.5">
                {queuedMessages.map((q, idx) => (
                  <div key={q.id} className="flex items-center gap-2 rounded-xl bg-[#05080F] border border-slate-700/40 px-2.5 py-2 group">
                    <span className="text-[11px] font-mono text-slate-500 shrink-0">#{idx + 1}</span>
                    <span className="flex-1 truncate text-xs text-slate-300" title={q.content}>
                      {q.content}
                    </span>
                    {q.contexts.length > 0 && <span className="hidden sm:inline text-[11px] text-slate-500 shrink-0">+{q.contexts.length} ctx</span>}
                    <button
                      onClick={() => removeQueued(q.id)}
                      className="h-6 w-6 shrink-0 grid place-items-center rounded-full text-slate-500 hover:bg-rose-500/10 hover:text-rose-400 transition-colors"
                      aria-label={`Remove queued: ${q.content.slice(0, 30)}`}
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Input row */}
          <div className="flex items-end gap-2 p-2">
            <button
              onClick={() => fileRef.current?.click()}
              className="h-8 w-8 shrink-0 rounded-[7px] grid place-items-center text-[#9aa39d] hover:text-[#e9ece9] hover:bg-[#181d1b] transition-colors focus-visible:ring-2 focus-visible:ring-[#06B6D4]/30 focus-visible:outline-none"
              aria-label="Attach files"
            >
              <Paperclip size={16} />
            </button>
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
              onClick={addAoi}
              className="h-8 w-8 shrink-0 rounded-[7px] grid place-items-center text-[#9aa39d] hover:text-[#e9ece9] hover:bg-[#181d1b] transition-colors hidden sm:grid focus-visible:ring-2 focus-visible:ring-[#06B6D4]/30 focus-visible:outline-none"
              aria-label="Add AOI"
            >
              <MapPin size={16} />
            </button>

            <TextareaAutosize
              autoFocus={autoFocus}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onFocus={() => setFocused(true)}
              onBlur={() => setFocused(false)}
              onKeyDown={onKeyDown}
              minRows={1}
              maxRows={7}
              placeholder={isBusy ? "Follow-up will be queued — Enter to queue, Esc to stop" : placeholder}
              aria-label="Message"
              className="composer-input flex-1 self-center bg-transparent text-[14px] leading-6 text-[#e9ece9] placeholder:text-[#5b655f] !outline-none focus:!outline-none ring-0 border-0 resize-none py-1.5 max-h-[168px] min-h-[22px] overflow-y-auto"
            />

            {isBusy ? (
              <button
                onClick={handleStop}
                className="h-8 w-8 rounded-[7px] grid place-items-center shrink-0 bg-rose-500/15 border border-rose-500/20 text-rose-400 hover:bg-rose-500/20 hover:text-rose-300 transition-all active:scale-95"
                aria-label="Stop generating"
                title="Stop generating (Esc)"
              >
                <Square size={13} className="fill-current" />
              </button>
            ) : (
              <button
                onClick={() => handleSend()}
                disabled={!canSend}
                className={cn(
                  "h-8 w-8 rounded-[7px] grid place-items-center shrink-0 transition-all",
                  canSend ? "bg-[#06B6D4] text-white hover:bg-[#0891B2] active:scale-95 shadow-[0_2px_10px_rgba(6,182,212,0.35)]" : "bg-[#1e2422] text-[#5b655f] cursor-not-allowed border border-[#242b28]"
                )}
                aria-label="Send"
                title="Send (Enter)"
              >
                <ArrowUp size={15} />
              </button>
            )}
            {/* queued-state send as Clock */}
            {isBusy && canSend && (
              <button
                onClick={() => handleSend()}
                className="h-8 w-8 rounded-[7px] grid place-items-center shrink-0 bg-amber-500 text-white hover:bg-amber-600 active:scale-95 transition-all"
                aria-label="Queue message"
                title="Queue (response in progress)"
              >
                <Clock3 size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="mt-1.5 flex items-center justify-between px-1 text-[10.5px] text-[#5b655f]">
          <span>{activeContexts.length ? `${activeContexts.length} context${activeContexts.length > 1 ? "s" : ""} attached` : "Enter to send · Shift+Enter for newline · Esc to stop"}</span>
          <span className="hidden sm:inline">
            {queuedMessages.length ? `${queuedMessages.length} queued` : isBusy ? <span className="inline-flex items-center gap-1 text-amber-400"><Loader2 size={10} className="animate-spin" /> generating…</span> : ""}
          </span>
        </div>

        {error && (
          <div className="mt-2 flex items-center gap-1.5 text-xs text-rose-400" role="alert" aria-live="polite">
            <AlertCircle size={14} />
            <span>{error}</span>
          </div>
        )}
      </div>
    );
  }
);

Composer.displayName = "Composer";
export default Composer;
