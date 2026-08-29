import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
  sources?: string[];
  thinking?: string;
  thinkingStreaming?: boolean;
  thinkingCollapsed?: boolean;
  contexts?: ChatContext[];
  createdAt?: number;
  followUpQuestions?: string[];
}
export interface ChatContext {
  id: string;
  type: string;
  label: string;
  confidence?: number;
  preview?: string;
  fileName?: string;
}

export interface QueuedMessage {
  id: string;
  content: string;
  contexts: ChatContext[];
  createdAt: number;
}

interface ChatState {
  messages: Message[];
  activeContexts: ChatContext[];
  queuedMessages: QueuedMessage[];
  addMessage: (m: Message) => void;
  appendChunk: (id: string, chunk: string) => void;
  setStreaming: (id: string, v: boolean) => void;
  appendThinking: (id: string, chunk: string) => void;
  setThinkingStreaming: (id: string, v: boolean) => void;
  setThinkingCollapsed: (id: string, v: boolean) => void;
  setFollowUpQuestions: (id: string, qs: string[]) => void;
  addContext: (c: ChatContext) => void;
  removeContext: (id: string) => void;
  clear: () => void;
  clearContexts: () => void;
  enqueue: (m: QueuedMessage) => void;
  dequeue: () => QueuedMessage | undefined;
  removeQueued: (id: string) => void;
  clearQueue: () => void;
  // helpers for session persistence (exposed but not persisted directly)
  setMessages: (msgs: Message[]) => void;
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      messages: [],
      activeContexts: [],
      queuedMessages: [],
      addMessage: (msg) =>
        set((s) => ({
          messages: [
            ...s.messages,
            { ...msg, createdAt: msg.createdAt ?? Date.now() },
          ],
        })),
      appendChunk: (id, chunk) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, content: m.content + chunk } : m)) })),
      setStreaming: (id, streaming) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, streaming } : m)) })),
      appendThinking: (id, chunk) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, thinking: (m.thinking ?? "") + chunk } : m)) })),
      setThinkingStreaming: (id, v) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, thinkingStreaming: v } : m)) })),
      setThinkingCollapsed: (id, v) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, thinkingCollapsed: v } : m)) })),
      setFollowUpQuestions: (id, qs) =>
        set((s) => ({ messages: s.messages.map((m) => (m.id === id ? { ...m, followUpQuestions: qs } : m)) })),
      addContext: (c) =>
        set((s) => (s.activeContexts.find((x) => x.id === c.id) ? s : { activeContexts: [...s.activeContexts, c] })),
      removeContext: (id) => set((s) => ({ activeContexts: s.activeContexts.filter((c) => c.id !== id) })),
      clear: () => set({ messages: [], activeContexts: [], queuedMessages: [] }),
      clearContexts: () => set({ activeContexts: [] }),
      enqueue: (m) =>
        set((s) => {
          if (s.queuedMessages.length >= 5) return s;
          return { queuedMessages: [...s.queuedMessages, m] };
        }),
      dequeue: () => {
        const s = get();
        if (s.queuedMessages.length === 0) return undefined;
        const out = s.queuedMessages[0];
        set({ queuedMessages: s.queuedMessages.slice(1) });
        return out;
      },
      removeQueued: (id) => set((s) => ({ queuedMessages: s.queuedMessages.filter((q) => q.id !== id) })),
      clearQueue: () => set({ queuedMessages: [] }),
      setMessages: (messages) => set({ messages }),
    }),
    {
      name: "satiq-chat-v1",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ messages: s.messages, queuedMessages: s.queuedMessages }),
      version: 1,
    }
  )
);
