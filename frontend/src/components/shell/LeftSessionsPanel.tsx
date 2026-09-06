import { useState, useMemo, useRef, useEffect } from "react";
import { Search, Plus, Clock3, Layers, Satellite, MapPin, Flame, MoreHorizontal, Pencil, Trash2, Check, X } from "lucide-react";
import { useChatStore } from "@/store/chat.store";
import { useWorkspaceStore } from "@/store/workspace.store";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useExecutionStore } from "@/store/execution.store";
import { updateSessionBackend } from "@/lib/sessionSync";
import { toast } from "sonner";

const CATEGORY_ICON: Record<string, typeof MapPin> = {
  change: Layers,
  fusion: Satellite,
  wildfire: Flame,
};

const CATEGORY_COLOR: Record<string, string> = {
  change: "#F59E0B",
  fusion: "#06B6D4",
  wildfire: "#EF4444",
  grounding: "#22C55E",
};

function loadMessagesFor(id: string) {
  try {
    const raw = localStorage.getItem(`satiq:session:${id}:messages`);
    if (raw) return JSON.parse(raw);
  } catch {}
  return null;
}

// Persist conversation to localStorage (authoritative offline) and mirror to backend (best-effort).
function persistMessages(id: string, messages: unknown[]) {
  try {
    localStorage.setItem(`satiq:session:${id}:messages`, JSON.stringify(messages));
  } catch {}
  void updateSessionBackend(id, { chatHistory: messages });
}

export function LeftSessionsPanel() {
  const [q, setQ] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [menuId, setMenuId] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const { clear, setMessages } = useChatStore();
  const { activeAnalysisId, setActiveAnalysisId, sessions, createSession, renameSession, deleteSession } = useWorkspaceStore();
  const { reset } = useExecutionStore();

  useEffect(() => {
    if (editingId && inputRef.current) inputRef.current.select();
  }, [editingId]);

  // Close menu on click outside
  useEffect(() => {
    const onClick = () => setMenuId(null);
    window.addEventListener("click", onClick);
    return () => window.removeEventListener("click", onClick);
  }, []);

  const filtered = useMemo(() => {
    const sorted = [...sessions].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());
    if (!q) return sorted;
    const lower = q.toLowerCase();
    return sorted.filter((a) => a.title.toLowerCase().includes(lower) || a.category.toLowerCase().includes(lower));
  }, [q, sessions]);

  const grouped: Record<string, typeof filtered> = useMemo(() => {
    const now = Date.now();
    const today: typeof filtered = [];
    const yesterday: typeof filtered = [];
    const earlier: typeof filtered = [];
    for (const s of filtered) {
      const diffDays = (now - new Date(s.updatedAt).getTime()) / 86400000;
      if (diffDays < 1) today.push(s);
      else if (diffDays < 2) yesterday.push(s);
      else earlier.push(s);
    }
    // If all in today but we had seed, keep structure
    if (!today.length && !yesterday.length) return { ALL: filtered } as any;
    return { TODAY: today, YESTERDAY: yesterday, EARLIER: earlier };
  }, [filtered]);

  const handleNew = () => {
    // C1: never leave dangling AbortController — cancel before switching
    // save current before switching
    if (activeAnalysisId) {
      persistMessages(activeAnalysisId, useChatStore.getState().messages);
    }
    const id = createSession();
    clear();
    reset();
    setActiveAnalysisId(id);
    toast.success("New chat started");
  };

  const handleSelect = (id: string) => {
    if (id === activeAnalysisId) return;
    // save current
    if (activeAnalysisId) {
      persistMessages(activeAnalysisId, useChatStore.getState().messages);
    }
    // load target
    const stored = loadMessagesFor(id);
    if (stored) setMessages(stored);
    else clear();
    reset();
    setActiveAnalysisId(id);
  };

  const startRename = (id: string, title: string) => {
    setEditingId(id);
    setEditValue(title);
    setMenuId(null);
  };
  const commitRename = () => {
    if (!editingId) return;
    const v = editValue.trim().slice(0, 60);
    if (!v) { setEditingId(null); return; }
    renameSession(editingId, v);
    setEditingId(null);
    toast.success("Renamed");
  };

  const handleDelete = (id: string) => {
    if (!confirm("Delete this chat? Messages will be lost.")) return;
    // C2: cancel generation if deleting the active session
    deleteSession(id);
    if (activeAnalysisId === id) {
      const next = useWorkspaceStore.getState().sessions[0];
      if (next) {
        const stored = loadMessagesFor(next.id);
        if (stored) setMessages(stored);
        else clear();
        reset();
        // ensure activeAnalysisId is set to next (store already does, but re-assert for message sync)
        setActiveAnalysisId(next.id);
      } else {
        // no sessions left -> create fresh empty one
        clear();
        reset();
        const freshId = createSession("New conversation");
        setActiveAnalysisId(freshId);
      }
    }
    setMenuId(null);
    toast.message("Chat deleted");
  };

  const handleClear = (id: string) => {
    persistMessages(id, []);
    if (activeAnalysisId === id) {
      clear();
      reset();
    }
    setMenuId(null);
    toast.success("Conversation cleared");
  };

  const handleDuplicate = (id: string) => {
    try {
      const srcRaw = localStorage.getItem(`satiq:session:${id}:messages`);
      const srcMsgs = srcRaw ? JSON.parse(srcRaw) : [];
      const srcSession = sessions.find((s) => s.id === id);
      const dupId = createSession(`${srcSession?.title ?? "Chat"} — copy`);
      persistMessages(dupId, Array.isArray(srcMsgs) ? srcMsgs : []);
      const stored = loadMessagesFor(dupId);
      if (stored) setMessages(stored);
      reset();
      setActiveAnalysisId(dupId);
      toast.success("Duplicated");
    } catch {
      toast.error("Duplicate failed");
    }
    setMenuId(null);
  };

  const handleExport = (id: string) => {
    try {
      const msgsRaw = localStorage.getItem(`satiq:session:${id}:messages`) ?? "[]";
      const session = sessions.find((s) => s.id === id);
      const payload = { session, messages: JSON.parse(msgsRaw), exportedAt: new Date().toISOString() };
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `satiq-${id}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success("Exported JSON");
    } catch {
      toast.error("Export failed");
    }
    setMenuId(null);
  };

  return (
    <div className="w-full h-full bg-[#0B1120] flex flex-col relative overflow-hidden">
      <div className="p-3 space-y-2.5">
        <button
          onClick={handleNew}
          className="w-full h-9 flex items-center justify-center gap-2 rounded-xl bg-[#06B6D4] text-white text-[13px] font-semibold hover:bg-[#0891B2] active:scale-[0.98] transition-all duration-150 shadow-[0_2px_12px_rgba(6,182,212,0.3)] focus-visible:ring-2 focus-visible:ring-[#06B6D4]/40 focus-visible:outline-none"
          aria-label="New chat"
        >
          <Plus size={15} strokeWidth={2.5} />
          New chat
        </button>

        <div className="relative">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600 pointer-events-none" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search sessions…"
            aria-label="Search sessions"
            className="w-full h-8 rounded-lg bg-[#05080F] border border-slate-700/40 pl-8 pr-3 text-[12.5px] text-slate-300 placeholder:text-slate-600 outline-none focus:border-[#06B6D4]/50 focus:bg-[#05080F] transition-colors"
          />
          {q && (
            <button onClick={() => setQ("")} className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300" aria-label="Clear search">
              <X size={12} />
            </button>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {Object.entries(grouped).map(([group, items]) =>
          (items as any).length ? (
            <div key={group} className="pb-3">
              <div className="px-2 py-1.5 text-[10px] font-semibold tracking-[0.1em] text-slate-600 uppercase">{group}</div>
              <div className="space-y-0.5">
                {(items as any).map((a: any) => {
                  const isActive = activeAnalysisId === a.id;
                  const Icon = CATEGORY_ICON[a.category as string] ?? MapPin;
                  const iconColor = CATEGORY_COLOR[a.category as string] ?? "#64748B";
                  const isEditing = editingId === a.id;

                  return (
                    <div
                      key={a.id}
                      className={cn(
                        "w-full text-left flex items-start gap-2.5 px-2.5 py-2.5 rounded-lg transition-all duration-150 relative group border",
                        isActive ? "bg-[#141F30] border-slate-700/50 shadow-sm" : "hover:bg-[#101827] border-transparent"
                      )}
                    >
                      {isActive && <span className="absolute left-0 top-3 bottom-3 w-[2.5px] bg-[#06B6D4] rounded-full" />}
                      <span className={cn("mt-0.5 h-6 w-6 rounded-md grid place-items-center shrink-0 transition-colors", isActive ? "bg-[#1A2740]" : "bg-[#101827] group-hover:bg-[#141F30]")}>
                        <Icon size={13} style={{ color: isActive ? iconColor : "#475569" }} />
                      </span>

                      <button
                        onClick={() => !isEditing && handleSelect(a.id)}
                        className="min-w-0 flex-1 text-left"
                        aria-label={`Open ${a.title}`}
                      >
                        {isEditing ? (
                          <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                            <input
                              ref={inputRef}
                              value={editValue}
                              onChange={(e) => setEditValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") commitRename();
                                if (e.key === "Escape") setEditingId(null);
                              }}
                              className="w-full h-6 rounded-md bg-[#05080F] border border-slate-700/40 px-2 text-[12px] text-slate-200 outline-none focus:border-[#06B6D4]/40"
                              autoFocus
                            />
                            <button onClick={commitRename} className="h-6 w-6 grid place-items-center rounded-md bg-[#06B6D4] text-white hover:bg-[#0891B2]"><Check size={12} /></button>
                            <button onClick={() => setEditingId(null)} className="h-6 w-6 grid place-items-center rounded-md bg-slate-800 text-slate-400 hover:text-white"><X size={12} /></button>
                          </div>
                        ) : (
                          <>
                            <span className={cn("block text-[13px] font-medium leading-tight truncate transition-colors", isActive ? "text-slate-100" : "text-slate-400 group-hover:text-slate-200")}>{a.title}</span>
                            <span className="flex items-center gap-1 text-[11px] text-slate-600 mt-0.5">
                              <span className="capitalize" style={{ color: isActive ? iconColor : undefined }}>{a.category}</span>
                              <span className="text-slate-700">·</span>
                              <Clock3 size={9} className="shrink-0" />
                              <span>{relativeTime(a.createdAt)}</span>
                            </span>
                          </>
                        )}
                      </button>

                      {!isEditing && (
                        <div className="relative shrink-0">
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setMenuId(menuId === a.id ? null : a.id);
                            }}
                            className={cn(
                              "h-6 w-6 rounded-md grid place-items-center text-slate-500 hover:text-slate-200 hover:bg-slate-800/60 transition-colors",
                              isActive ? "opacity-100" : "opacity-0 group-hover:opacity-100",
                              menuId === a.id && "opacity-100 bg-slate-800/60 text-slate-200"
                            )}
                            aria-label={`Actions for ${a.title}`}
                            aria-haspopup="menu"
                          >
                            <MoreHorizontal size={13} />
                          </button>
                          {menuId === a.id && (
                            <div className="absolute right-0 top-7 z-30 w-44 rounded-xl border border-slate-700/50 bg-[#0B1120] shadow-[0_12px_40px_rgba(0,0,0,0.6)] p-1" role="menu" onClick={(e) => e.stopPropagation()}>
                              <button onClick={() => startRename(a.id, a.title)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-slate-300 hover:text-white hover:bg-[#141F30] transition-colors" role="menuitem">
                                <Pencil size={12} /> Rename
                              </button>
                              <button onClick={() => handleClear(a.id)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-slate-400 hover:text-white hover:bg-[#141F30] transition-colors" role="menuitem">
                                <Trash2 size={12} /> Clear conversation
                              </button>
                              <button onClick={() => handleDuplicate(a.id)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-slate-300 hover:text-white hover:bg-[#141F30] transition-colors" role="menuitem">
                                <span className="text-[11px]">⧉</span> Duplicate
                              </button>
                              <button onClick={() => handleExport(a.id)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-slate-300 hover:text-white hover:bg-[#141F30] transition-colors" role="menuitem">
                                <span className="text-[11px]">⤓</span> Export JSON
                              </button>
                              <div className="my-1 h-px bg-slate-800/60" />
                              <button onClick={() => handleDelete(a.id)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-xs text-rose-400 hover:text-rose-300 hover:bg-rose-500/10 transition-colors" role="menuitem">
                                <Trash2 size={12} /> Delete
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ) : null
        )}
        {filtered.length === 0 && (
          <div className="px-4 py-8 text-center">
            <div className="text-xs text-slate-600">No sessions match</div>
            <div className="text-[11px] text-slate-700 mt-1 font-mono">"{q}"</div>
            {q && <button onClick={() => setQ("")} className="mt-3 text-xs text-[#06B6D4] hover:underline">Clear search</button>}
          </div>
        )}
      </div>

      <div className="p-3 border-t border-slate-800/50 flex items-center gap-2.5">
        <div className="h-7 w-7 rounded-full bg-[#101827] border border-slate-700/40 grid place-items-center shrink-0">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="#334155" strokeWidth="1" />
            <circle cx="7" cy="7" r="2" fill="#06B6D4" opacity="0.6" />
            <line x1="7" y1="1.5" x2="7" y2="4" stroke="#334155" strokeWidth="1" strokeLinecap="round" />
            <line x1="7" y1="10" x2="7" y2="12.5" stroke="#334155" strokeWidth="1" strokeLinecap="round" />
            <line x1="1.5" y1="7" x2="4" y2="7" stroke="#334155" strokeWidth="1" strokeLinecap="round" />
            <line x1="10" y1="7" x2="12.5" y2="7" stroke="#334155" strokeWidth="1" strokeLinecap="round" />
          </svg>
        </div>
        <div className="min-w-0">
          <div className="text-[12px] font-semibold text-slate-300 leading-none">Satiq OS</div>
          <div className="text-[10.5px] text-slate-600 mt-0.5">{sessions.length} sessions · Encrypted</div>
        </div>
        <span className="ml-auto h-2 w-2 rounded-full bg-[#22C55E] shrink-0" style={{ boxShadow: "0 0 6px rgba(34,197,94,0.7)" }} />
      </div>
    </div>
  );
}
