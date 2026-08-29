import { useEffect } from "react";
import { useChatStore } from "@/store/chat.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { toast } from "sonner";

const keyFor = (id: string) => `satiq:session:${id}:messages`;

export function useSessionPersistence() {
  const activeId = useWorkspaceStore((s) => s.activeAnalysisId);
  const messages = useChatStore((s) => s.messages);
  const setMessages = useChatStore((s) => s.setMessages);

  // load when active changes — handle corrupted JSON gracefully
  useEffect(() => {
    if (!activeId) return;
    try {
      const raw = localStorage.getItem(keyFor(activeId));
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          const current = useChatStore.getState().messages;
          if (JSON.stringify(current) !== JSON.stringify(parsed)) {
            setMessages(parsed);
          }
          return;
        }
        // unexpected shape -> treat as corrupted
        throw new Error("not an array");
      }
    } catch (e) {
      console.warn("[session] corrupted storage for", activeId, e);
      toast.error("Session data was corrupted — starting fresh");
      try { localStorage.setItem(keyFor(activeId), JSON.stringify([])); } catch {}
      setMessages([]);
    }
  }, [activeId, setMessages]);

  // save on messages change (debounced 300ms) — always save as non-streaming so restore does NOT re-animate
  useEffect(() => {
    if (!activeId) return;
    const t = setTimeout(() => {
      try {
        const toSave = messages.map((m: any) => ({ ...m, streaming: false, thinkingStreaming: false }));
        localStorage.setItem(keyFor(activeId), JSON.stringify(toSave));
      } catch (e) {
        console.warn("[session] save failed", e);
      }
    }, 300);
    return () => clearTimeout(t);
  }, [activeId, messages]);

  // C4: force-save on page unload — also as non-streaming
  useEffect(() => {
    const onBeforeUnload = () => {
      if (!activeId) return;
      try {
        const cur = useChatStore.getState().messages.map((m: any) => ({ ...m, streaming: false, thinkingStreaming: false }));
        localStorage.setItem(keyFor(activeId), JSON.stringify(cur));
      } catch {}
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [activeId]);
}
