import { useChatStore } from "@/store/chat.store";
import { useExecutionStore } from "@/store/execution.store";
import { MessageItem } from "./MessageItem";
import { ConversationSeed } from "./ConversationSeed";
import { Composer } from "./Composer";
import { useAutoScroll } from "@/hooks/useAutoScroll";
import { MessageTypingIndicator } from "@/components/ui/skeleton";

const BUSY = ["queued", "planning", "executing", "aggregating", "composing"];

export function ChatCanvas() {
  const { messages } = useChatStore();
  const { globalStatus } = useExecutionStore();
  const isBusy = BUSY.includes(globalStatus);
  const hasStreaming = messages.some((m) => m.role === "assistant" && (m.streaming || m.thinkingStreaming));
  const hasAssistant = messages.some((m) => m.role === "assistant");
  const empty = messages.length === 0;

  const { containerRef } = useAutoScroll([messages, globalStatus]);

  if (empty) return <ConversationSeed />;

  return (
    <div className="flex flex-col h-full bg-[#090D14] relative overflow-hidden">
      <div ref={containerRef} className="flex-1 overflow-y-auto px-6 py-4 space-y-6">
        <div className="mx-auto w-full max-w-[780px] space-y-6">
          {messages.map((m) => (
            <MessageItem key={m.id} message={m} />
          ))}
          {/* Initial request: only typing indicator under last user message, no skeleton cards */}
          {isBusy && !hasAssistant && <div className="pl-10"><MessageTypingIndicator /></div>}
          {/* Fallback for gap between steps where no assistant yet but pipeline running - also typing only */}
          {isBusy && !hasStreaming && hasAssistant && messages[messages.length - 1]?.role === "user" && (
            <div className="pl-10"><MessageTypingIndicator /></div>
          )}
        </div>
      </div>

      <div className="shrink-0 p-4 bg-[#090D14]/80 backdrop-blur border-t border-slate-800/60">
        <div className="mx-auto max-w-[780px]">
          <Composer />
        </div>
      </div>
    </div>
  );
}
