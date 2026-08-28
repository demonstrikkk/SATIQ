import { useState } from "react";
import { User, Bot, Copy, Check, PanelRightOpen, Layers3 } from "lucide-react";
import type { Message } from "@/store/chat.store";
import { MessageCard, MessageCardSkeleton, ActionChip } from "./MessageCard";
import { MessageTypingIndicator } from "@/components/ui/skeleton";
import { StreamingResponseCard } from "./StreamingResponseCard";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useMapStore } from "@/store/map.store";
import { useExecutionStore } from "@/store/execution.store";

function confidenceOf(content: string): number | null {
  const m = content.match(/Confidence:\s*([0-9.]+)/i);
  if (!m) return null;
  const v = parseFloat(m[1]);
  return isNaN(v) ? null : v > 1 ? v / 100 : v;
}

function capabilityOf(content: string): string {
  const c = content.toLowerCase();
  if (c.includes("fused") || c.includes("sar") || c.includes("optical")) return "Fusion";
  if (c.includes("bbox") || c.includes("ground") || c.includes("detect")) return "Grounding";
  if (c.includes("change") || c.includes("sector") || c.includes("shoreline")) return "Change";
  return "VQA";
}

function ThinkingBlock({ message }: { message: Message }) {
  // Now handled via StreamingResponseCard; keep stub for backward compat
  return null;
}

export function MessageItem({ message }: { message: Message }) {
  const isUser = message.role === "user";
  const { toggleInspector, inspectorOpen } = useWorkspaceStore();
  const { setSelectedFeatureId } = useMapStore();
  const [copied, setCopied] = useState(false);

  if (isUser) {
    return (
      <div className="flex justify-end animate-in fade-in slide-in-from-bottom-1 duration-200">
        <div className="flex items-start gap-2.5 max-w-[75%] w-auto justify-end">
          <div className="min-w-0 max-w-[560px] w-auto flex flex-col items-end">
            <div className="flex items-center gap-2 mb-1 justify-end w-fit">
              <span className="text-[11px] font-semibold tracking-[0.08em] uppercase text-slate-400">You</span>
            </div>
            <MessageCard variant="user" className="w-fit max-w-full ml-auto">
              <div className="text-[14px] leading-relaxed text-slate-100 whitespace-pre-wrap break-words [overflow-wrap:anywhere]">{message.content}</div>
              {message.contexts && message.contexts.length > 0 && (
                <div className="mt-2.5 flex flex-wrap gap-2 justify-end">
                  {message.contexts.map((c) => (
                    <span key={c.id} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-700/60 bg-[#0D121F] px-2 py-1.5 text-xs text-slate-300">
                      {c.preview ? (
                        <img src={c.preview} alt={c.label} className="h-8 w-8 rounded object-cover border border-slate-700 shrink-0" />
                      ) : c.type === "aoi" ? (
                        <span className="h-8 w-8 rounded bg-[#06B6D4]/15 border border-[#06B6D4]/20 grid place-items-center shrink-0">
                          <PanelRightOpen size={14} className="text-[#06B6D4]" />
                        </span>
                      ) : (
                        <span className="h-8 w-8 rounded bg-slate-800/60 grid place-items-center shrink-0">
                          <Layers3 size={14} className="text-slate-400" />
                        </span>
                      )}
                      <span className="truncate max-w-[120px]">{c.label}</span>
                    </span>
                  ))}
                </div>
              )}
            </MessageCard>
          </div>
          <span className="h-7 w-7 rounded-full grid place-items-center border border-slate-800/60 bg-[#0D121F] text-slate-300 shrink-0 mt-1">
            <User size={13} />
          </span>
        </div>
      </div>
    );
  }

  const conf = confidenceOf(message.content);
  const capability = capabilityOf(message.content);
  const streaming = !!message.streaming;
  const thinkingStreaming = !!message.thinkingStreaming;
  const hasThinking = !!message.thinking;
  const hasContent = message.content.trim().length > 6;
  const isWaitingForFirstToken = (streaming || thinkingStreaming) && !hasThinking && !hasContent;
  const { pipelineSteps } = useExecutionStore();

  const copy = () => {
    navigator.clipboard?.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1400);
  };

  const openInspector = () => {
    // Derive bbox from latest assistant content if present, else fallback to generic id
    const m = message.content.match(/\[?\[?bbox[:\s]*([0-9.,\s-]+)/i);
    const coords = m?.[1]?.replace(/\s/g, "") ?? "inspect";
    const featureId = `bbox_${coords}`;
    setSelectedFeatureId(featureId);
    if (!inspectorOpen) toggleInspector();
  };

  // Adapter: Satiq thinking steps from pipeline for StreamingResponseCard
  const thinkingSteps = pipelineSteps.map(s => ({
    name: s.title,
    duration: s.durationMs,
    status: s.status as any,
  }));

  return (
    <div className="flex justify-start animate-in fade-in slide-in-from-bottom-1 duration-200 w-full">
      <div className="flex items-start gap-3 min-w-0 w-full">
        <span className="h-7 w-7 rounded-full grid place-items-center border border-[#06B6D4]/20 bg-[#06B6D4]/10 text-[#06B6D4] shrink-0 mt-1">
          <Bot size={13} />
        </span>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[11px] font-semibold tracking-[0.08em] uppercase text-slate-300">Satiq</span>
            <span className="inline-flex items-center gap-1 rounded-full border border-slate-800/60 bg-[#0D121F] px-2 py-0.5 text-[10px] text-slate-300">
              <Layers3 size={9} className="text-[#60A5FA]" /> {capability}
            </span>
            {conf !== null && (
              <span className="inline-flex items-center gap-1 rounded-full border border-[#22C55E]/20 bg-[#22C55E]/10 px-2 py-0.5 text-[10px] text-[#22C55E] font-medium">
                {Math.round(conf * 100)}% conf
              </span>
            )}
            <span className="text-[11px] text-slate-500">· now</span>
          </div>

          {isWaitingForFirstToken ? (
            <MessageTypingIndicator />
          ) : hasThinking || hasContent ? (
            <StreamingResponseCard
              thinking={message.thinking}
              thinkingStreaming={thinkingStreaming}
              markdownContent={message.content}
              isStreaming={streaming}
              thinkingSteps={thinkingSteps}
            />
          ) : (
            <MessageCardSkeleton />
          )}

          {!streaming && hasContent && (
            <div className="flex items-center gap-1.5 flex-wrap">
              <ActionChip onClick={copy} icon={copied ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}>
                {copied ? "Copied" : "Copy"}
              </ActionChip>
              <ActionChip onClick={openInspector} icon={<PanelRightOpen size={12} />}>
                Inspect on map
              </ActionChip>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
