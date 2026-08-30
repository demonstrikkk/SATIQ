import { useState, useEffect } from "react";
import { Copy, Check, PanelRightOpen, Layers3, Maximize2, RefreshCw, Map, Volume2, VolumeX, Pencil } from "lucide-react";
import { motion } from "framer-motion";
import { useChatStore } from "@/store/chat.store";
import type { Message } from "@/store/chat.store";
import { MessageCard, MessageCardSkeleton, ActionChip } from "./MessageCard";
import { MessageTypingIndicator } from "@/components/ui/skeleton";
import { StreamingResponseCard } from "./StreamingResponseCard";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useMapStore } from "@/store/map.store";
import { useExecutionStore } from "@/store/execution.store";
import { ChatImageLightbox } from "@/components/imagery/ChatImageLightbox";
import { executeRealAnalysis } from "@/lib/analysisClient";
import { toast } from "sonner";

// SATIQ mark — 26px square 6px radius per satquery-ai.html .msg-avatar
function SatiqBotMark() {
  return (
    <div className="h-[26px] w-[26px] rounded-[6px] flex items-center justify-center bg-[#101827] border border-slate-700/40 shrink-0">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#06B6D4" strokeWidth="1.6">
        <circle cx="12" cy="12" r="8.5" />
        <ellipse cx="12" cy="12" rx="8.5" ry="3.4" opacity="0.5" />
      </svg>
    </div>
  );
}

function UserAvatarMark() {
  return (
    <div className="h-[26px] w-[26px] rounded-full flex items-center justify-center bg-[#101827] border border-slate-700/40 shrink-0 font-mono text-[10.5px] font-semibold text-slate-400">
      Y
    </div>
  );
}

function confidenceOf(content: string): number | null {
  const m = content.match(/Confidence:\s*([0-9.]+)/i);
  if (!m) return null;
  const v = parseFloat(m[1]);
  return isNaN(v) ? null : v > 1 ? v / 100 : v;
}

function capabilityOf(content: string): { label: string; color: string } {
  const c = content.toLowerCase();
  if (c.includes("fused") || c.includes("sar") || c.includes("optical"))
    return { label: "Fusion", color: "#8B5CF6" };
  if (c.includes("bbox") || c.includes("ground") || c.includes("detect"))
    return { label: "Grounding", color: "#22C55E" };
  if (c.includes("change") || c.includes("sector") || c.includes("shoreline"))
    return { label: "Change", color: "#F59E0B" };
  return { label: "VQA", color: "#06B6D4" };
}

export function MessageItem({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const { toggleInspector, inspectorOpen } = useWorkspaceStore();
  const { setSelectedFeatureId } = useMapStore();
  const [copied, setCopied] = useState(false);
  const [viewer, setViewer] = useState<{ src: string; alt: string } | null>(null);
  const [imgLoaded, setImgLoaded] = useState<Record<string, boolean>>({});
  const [speaking, setSpeaking] = useState(false);

  useEffect(() => {
    return () => {
      try {
        window.speechSynthesis?.cancel();
      } catch {}
    };
  }, []);

  // ── Text-to-speech (client Web Speech API) for assistant answers ──
  const speak = () => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      toast.message("Text-to-speech not supported in this browser");
      return;
    }
    if (speaking) {
      window.speechSynthesis.cancel();
      setSpeaking(false);
      return;
    }
    const text = message.content
      .replace(/```chart[\s\S]*?```/gi, " ")
      .replace(/```[\s\S]*?```/gi, " ")
      .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
      .replace(/[#>*_`-]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    if (!text) return;
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 1;
    u.pitch = 1;
    u.onend = () => setSpeaking(false);
    u.onerror = () => setSpeaking(false);
    setSpeaking(true);
    window.speechSynthesis.speak(u);
  };

  // ── User message — A3 motion: fade + y6, 0.2s
  if (isUser) {
    return (
      <>
        {viewer && <ChatImageLightbox image={{ src: viewer.src, alt: viewer.alt, label: viewer.alt }} onClose={() => setViewer(null)} />}
        <motion.div
          id={`msg-${message.id}`}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
          className="flex justify-end"
        >
          <div className="flex items-start gap-3 max-w-[72%] justify-end">
            <div className="min-w-0 max-w-[640px] flex flex-col items-end gap-2">
              <div className="text-[11.5px] font-semibold text-slate-400 leading-none self-end">You</div>
              {message.contexts && message.contexts.length > 0 && (
                <div className="flex flex-wrap gap-2 justify-end">
                  {message.contexts.map((c) => {
                    const isSar = /sar/i.test(c.label);
                    const isOptical = /optical/i.test(c.label);
                    const isImg = !!c.preview;
                    return (
                      <div
                        key={c.id}
                        className="w-[160px] rounded-[8px] border border-[#323a36] bg-[#121615] overflow-hidden text-left group"
                        onClick={() => isImg && c.preview && setViewer({ src: c.preview!, alt: c.label })}
                        role={isImg ? "button" : undefined}
                        tabIndex={isImg ? 0 : undefined}
                        onKeyDown={(e) => { if (e.key === "Enter" && isImg && c.preview) setViewer({ src: c.preview!, alt: c.label }); }}
                      >
                        <div className={`h-[62px] w-full bg-[#0d1210] overflow-hidden relative ${isImg ? "cursor-zoom-in" : ""}`}>
                          {c.preview ? (
                            <>
                              {!imgLoaded[c.id] && <div className="absolute inset-0 bg-[#0B1120] animate-pulse" />}
                              <img
                                src={c.preview}
                                alt={c.label}
                                className={`h-full w-full object-cover transition-opacity duration-300 ${imgLoaded[c.id] ? "opacity-100" : "opacity-0"}`}
                                loading="lazy"
                                onLoad={() => setImgLoaded((s) => ({ ...s, [c.id]: true }))}
                                onError={() => setImgLoaded((s) => ({ ...s, [c.id]: true }))}
                              />
                              <div className="absolute inset-0 hidden group-hover:grid place-items-center bg-black/30 backdrop-blur-[1px] transition-colors">
                                <span className="inline-flex items-center gap-1 rounded-full bg-black/60 border border-white/20 px-2 py-1 text-[10px] text-white"><Maximize2 size={10} /> View</span>
                              </div>
                            </>
                          ) : c.type === "aoi" ? (
                            <div className="h-full w-full grid place-items-center bg-[#0b0f0d]">
                              <PanelRightOpen size={14} className="text-[#06B6D4]" />
                            </div>
                          ) : (
                            <div className="h-full w-full grid place-items-center bg-[#0b0f0d] text-[9px] font-mono text-slate-500">no preview</div>
                          )}
                        </div>
                        <div className="px-2 py-1.5">
                          <div className="font-mono text-[10.5px] text-[#e9ece9] truncate leading-none">{c.label}</div>
                          <div className="mt-1 flex items-center gap-1">
                            {isSar ? (
                              <span className="text-[9.5px] font-semibold uppercase px-1.5 py-0.5 rounded-[3px] bg-[rgba(217,164,65,0.12)] text-[#d9a441]">SAR</span>
                            ) : isOptical ? (
                              <span className="text-[9.5px] font-semibold uppercase px-1.5 py-0.5 rounded-[3px] bg-[rgba(91,141,191,0.12)] text-[#8db3dd]">Optical</span>
                            ) : c.type === "aoi" ? (
                              <span className="text-[9.5px] font-semibold uppercase px-1.5 py-0.5 rounded-[3px] bg-[rgba(6,182,212,0.10)] text-[#06B6D4]">AOI</span>
                            ) : isImg ? (
                              <span className="text-[9.5px] font-semibold uppercase px-1.5 py-0.5 rounded-[3px] bg-[#06B6D4]/15 text-[#06B6D4]">IMG</span>
                            ) : null}
                            <span className="text-[9.5px] font-mono text-[#5b655f]">10m{isImg ? " · tap to view" : ""}</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            <div className="rounded-[10px] rounded-br-[2px] border border-slate-700/40 bg-[#181d1b] px-4 py-3 max-w-full">
              <div className="text-[14px] leading-[1.65] text-[#e9ece9] whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {message.content}
              </div>
            </div>
            <ActionChip
              onClick={() => useChatStore.getState().setComposerPrefill(message.content)}
              icon={<Pencil size={11} />}
            >
              Edit
            </ActionChip>
          </div>
          <div className="mt-0.5 shrink-0">
            <UserAvatarMark />
          </div>
        </div>
      </motion.div>
      </>
    );
  }

  // ── Assistant message ─────────────────────────────────────────────────────────
  const conf = confidenceOf(message.content);
  const capability = capabilityOf(message.content);
  const streaming = !!message.streaming;
  const thinkingStreaming = !!message.thinkingStreaming;
  const hasThinking = !!message.thinking;
  const hasContent = message.content.trim().length > 6;
  const isWaitingForFirstToken = (streaming || thinkingStreaming) && !hasThinking && !hasContent;
  const { pipelineSteps, globalStatus } = useExecutionStore();

  const copy = async () => {
    try {
      await navigator.clipboard?.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {}
  };

  const openInspector = () => {
    const m = message.content.match(/\[?\[?bbox[:\s]*([0-9.,\s-]+)/i);
    const coords = m?.[1]?.replace(/\s/g, "") ?? "inspect";
    const featureId = `bbox_${coords}`;
    setSelectedFeatureId(featureId);
    if (!inspectorOpen) toggleInspector();
  };

  const thinkingSteps = pipelineSteps.map((s) => ({
    name: s.title,
    duration: s.durationMs,
    status: s.status as any,
  }));
  const isGenerating = ["queued","planning","executing","aggregating","composing"].includes(globalStatus);
  const hasSpatial = /bbox|Box|coords|\[.*\d+.*,\s*\d+.*\]/i.test(message.content) || message.content.includes("EPSG");
  const canRegenerate = !streaming && !isGenerating && hasContent;

  const handleRegenerate = () => {
    if (isGenerating) return;
    // find last user message for this assistant turn
    const msgs = useChatStore.getState().messages;
    const idx = msgs.findIndex((m) => m.id === message.id);
    let lastUser: Message | null = null;
    for (let i = idx - 1; i >= 0; i--) { if (msgs[i].role === "user") { lastUser = msgs[i]; break; } }
    if (!lastUser) { toast.error("No source message to regenerate"); return; }
    // re-run the same query through the real agentic pipeline
    useChatStore.getState().addMessage({ id: Date.now().toString(), role: "user", content: lastUser.content, contexts: lastUser.contexts ?? [] });
    void executeRealAnalysis(lastUser.content, (lastUser.contexts ?? []) as any).catch((e) => console.error("[analysis]", e));
    toast.success("Regenerating…");
  };

  const handleOpenInMap = () => {
    // ensure layers on and fly to first bbox
    const m = message.content.match(/\[([0-9.\s,;-]+)\]/);
    if (m) {
      const coords = m[1].replace(/\s/g, "");
      const featureId = `bbox_${coords}`;
      useMapStore.getState().addFeature({ id: featureId, label: "Regenerated view", confidence: 0.82, source: "LLM", type: "bbox" } as any);
      setSelectedFeatureId(featureId);
    }
    // toggle relevant layer
    const store = useMapStore.getState();
    if (!store.layers.detections) store.toggleLayer("detections");
    if (!inspectorOpen) toggleInspector();
  };

  return (
    <motion.div
      id={`msg-${message.id}`}
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
      className="flex justify-start w-full"
    >
      <div className="flex items-start gap-3 min-w-0 w-full">
        <div className="shrink-0 mt-0.5">
          <SatiqBotMark />
        </div>

        <div className="min-w-0 flex-1 max-w-[640px] space-y-3">
          {/* Header — html .msg-name: 11.5 semibold text-dim */}
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11.5px] font-semibold text-slate-400">SatQuery AI</span>
            <span
              className="inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-medium"
              style={{
                color: capability.color,
                borderColor: `${capability.color}30`,
                background: `${capability.color}14`,
              }}
            >
              <Layers3 size={9} />
              {capability.label}
            </span>
            {conf !== null && (
              <span className="inline-flex items-center gap-1 rounded-full border border-[#22C55E]/20 bg-[#22C55E]/10 px-2 py-0.5 text-[10px] text-[#22C55E] font-medium">
                {Math.round(conf * 100)}% conf
              </span>
            )}
            <span className="text-[10.5px] text-slate-600">· now</span>
          </div>

          {/* Message content */}
          {isWaitingForFirstToken ? (
            <MessageTypingIndicator />
          ) : hasThinking || hasContent ? (
            <StreamingResponseCard
              thinking={message.thinking}
              thinkingStreaming={thinkingStreaming}
              markdownContent={message.content}
              isStreaming={streaming}
              thinkingSteps={thinkingSteps}
              modelLabel={message.model}
            />
          ) : (
            <MessageCardSkeleton />
          )}

          {/* Actions — B5: Copy | Inspect | Open in map | Regenerate, disabled while generating */}
          {!streaming && hasContent && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <ActionChip
                onClick={copy}
                icon={copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
              >
                {copied ? "Copied" : "Copy"}
              </ActionChip>
              <ActionChip
                onClick={speak}
                icon={speaking ? <VolumeX size={11} className="text-[#06B6D4]" /> : <Volume2 size={11} />}
              >
                {speaking ? "Stop" : "Listen"}
              </ActionChip>
              <ActionChip onClick={openInspector} icon={<PanelRightOpen size={11} />}>
                Inspect on map
              </ActionChip>
              {hasSpatial && (
                <ActionChip onClick={handleOpenInMap} icon={<Map size={11} />}>
                  Open in map
                </ActionChip>
              )}
              <ActionChip
                onClick={handleRegenerate}
                icon={<RefreshCw size={11} className={isGenerating ? "opacity-50" : ""} />}
                // disabled visual via opacity + pointer
              >
                <span className={canRegenerate ? "" : "opacity-50"}>Regenerate</span>
              </ActionChip>
            </div>
          )}
          {/* LLM follow-up questions — clickable, chat-only (no tabs above input) */}
          {!streaming && message.followUpQuestions && message.followUpQuestions.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1" aria-label="Follow-up questions">
              {message.followUpQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => {
                    const { addMessage } = useChatStore.getState();
                    addMessage({ id: Date.now().toString(), role: "user", content: q });
                    void executeRealAnalysis(q, []).catch((e) => console.error("[analysis]", e));
                    if (isGenerating) toast.message("Queued — will run after current");
                  }}
                  className="rounded-full border border-slate-700/40 bg-[#0B1120] px-3 py-1.5 text-xs text-slate-300 hover:bg-[#141F30] hover:text-white hover:border-slate-600/50 transition-colors text-left max-w-full truncate"
                >
                  {q}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
