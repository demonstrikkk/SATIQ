import { useEffect, useMemo, useState, useRef } from "react";
import { useChatStore } from "@/store/chat.store";
import { useExecutionStore } from "@/store/execution.store";
import { MessageItem } from "./MessageItem";
import { ConversationSeed } from "./ConversationSeed";
import { Composer } from "./Composer";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { MessageTypingIndicator } from "@/components/ui/skeleton";
import { ArrowDown, AlertTriangle, RotateCcw } from "lucide-react";
import { cancelCurrentQuery } from "@/mocks/mockStream";
import { executeRealAnalysis, cancelCurrentAnalysis } from "@/lib/analysisClient";

const BUSY = ["queued", "planning", "executing", "aggregating", "composing"];

export function ChatCanvas() {
  const { messages } = useChatStore();
  const { globalStatus } = useExecutionStore();
  const isBusy = BUSY.includes(globalStatus);
  const hasStreaming = messages.some((m) => m.role === "assistant" && (m.streaming || m.thinkingStreaming));
  const hasAssistant = messages.some((m) => m.role === "assistant");
  const empty = messages.length === 0;

  const { containerRef, isPinned, forceScrollToBottom } = useAutoScroll([messages, globalStatus]);

  const [unseen, setUnseen] = useState(0);
  const prevLengthRef = useRef(messages.length);

  // Track unseen: increment only when new messages/chunks arrive while user has scrolled away (not pinned)
  useEffect(() => {
    const prev = prevLengthRef.current;
    const cur = messages.length;
    // New message added
    if (cur > prev) {
      if (!isPinned) {
        // count each new top-level message as 1 unseen; streaming chunk appends don't change length, so use length delta
        setUnseen((v) => v + (cur - prev));
      } else {
        setUnseen(0);
      }
    } else if (cur < prev) {
      // messages cleared (new chat) -> reset
      setUnseen(0);
    }
    prevLengthRef.current = cur;
  }, [messages.length, isPinned]);

  // While streaming, content grows without length change (appendChunk). If user is unpinned, show indicator.
  // Detect growth via last message content length tick
  const lastContentLen = messages[messages.length - 1]?.content.length ?? 0;
  const lastThinkingLen = (messages[messages.length - 1] as any)?.thinking?.length ?? 0;
  useEffect(() => {
    if (!isPinned && hasStreaming) {
      // subtle bump to keep dot visible; don't spam unseen for chunk growth
      // keep unseen as at least 1 while streaming away from bottom
      setUnseen((v) => (v === 0 ? 1 : v));
    }
  }, [lastContentLen, lastThinkingLen, isPinned, hasStreaming]);

  useEffect(() => {
    if (isPinned) setUnseen(0);
  }, [isPinned]);

  const showScrollButton = !isPinned;

  if (empty) return <ConversationSeed />;

  return (
    <div className="flex flex-col h-full relative overflow-hidden satiq-conversation-scroll">
      {/* Top fade */}
      <div
        className="absolute top-0 left-0 right-0 h-10 pointer-events-none z-10"
        style={{ background: "linear-gradient(to bottom, #05080F 0%, rgba(5,8,15,0.55) 55%, transparent 100%)" }}
      />

      {/* Message list — A2: 840px width, py-6, gap-5 rhythm; NOTE: no scroll-smooth here — auto uses instant, force uses smooth */}
      <div ref={containerRef} className="flex-1 overflow-y-auto" aria-live="polite" aria-label="Conversation">
        <div className="mx-auto w-full max-w-[840px] px-6 py-6 flex flex-col gap-5">
          {messages.map((m) => (
            <MessageItem key={m.id} message={m} />
          ))}
          {isBusy && !hasAssistant && (
            <div className="pl-10">
              <MessageTypingIndicator />
            </div>
          )}
          {isBusy && !hasStreaming && hasAssistant && messages[messages.length - 1]?.role === "user" && (
            <div className="pl-10">
              <MessageTypingIndicator />
            </div>
          )}
          {(globalStatus === "failed" || globalStatus === "cancelled") && (
            <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 flex items-start gap-3">
              <span className="h-7 w-7 rounded-lg bg-rose-500/15 border border-rose-500/20 grid place-items-center shrink-0">
                <AlertTriangle size={13} className="text-rose-400" />
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-[13px] font-medium text-rose-200">Generation {globalStatus === "cancelled" ? "stopped" : "failed"}</div>
                <div className="text-xs text-rose-300/70 mt-1">The last request was interrupted. You can retry with the same prompt.</div>
              </div>
              <button
                onClick={() => {
                  const lastUser = [...messages].reverse().find((m) => m.role === "user");
                  if (!lastUser) return;
                  // clear failed status then retry
                  const { reset } = useExecutionStore.getState();
                  reset();
                  useChatStore.getState().addMessage({ id: Date.now().toString(), role: "user", content: lastUser.content, contexts: lastUser.contexts ?? [] });
                  void executeRealAnalysis(lastUser.content, (lastUser.contexts ?? []) as any).catch((e) => console.error("[analysis]", e));
                }}
                className="shrink-0 inline-flex items-center gap-1.5 rounded-full bg-rose-500 text-white px-3 py-1.5 text-xs font-medium hover:bg-rose-600 transition-colors"
              >
                <RotateCcw size={12} /> Retry
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Floating: Scroll to bottom (command override) + Stop */}
      <div className="pointer-events-none absolute inset-x-0 bottom-[88px] flex flex-col items-center gap-2 z-20">
        {showScrollButton && (
          <button
            onClick={() => {
              forceScrollToBottom();
              setUnseen(0);
            }}
            className="pointer-events-auto h-9 w-9 rounded-full bg-[#0B1120] border border-slate-700/40 grid place-items-center shadow-[0_8px_28px_rgba(0,0,0,0.55)] hover:bg-[#141F30] hover:border-slate-600/50 transition-all"
            aria-label="Scroll to bottom"
            title="Scroll to bottom"
          >
            <ArrowDown size={16} className="text-[#06B6D4]" />
          </button>
        )}
        {isBusy && hasStreaming && (
          <button
            onClick={async () => {
              try { if (await cancelCurrentAnalysis()) return; } catch {}
              cancelCurrentQuery();
            }}
            className="pointer-events-auto inline-flex items-center gap-1.5 rounded-full bg-[#121615] border border-rose-500/20 px-3 py-1.5 text-xs font-medium text-rose-300 shadow-lg hover:bg-rose-500/10 transition-colors"
          >
            Stop generating
          </button>
        )}
      </div>

      {/* Composer area */}
      <div className="shrink-0 ">
        <div className="mx-auto max-w-[840px] px-6 py-3">
          <Composer />
        </div>
      </div>
    </div>
  );
}
