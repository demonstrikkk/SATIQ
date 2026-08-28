import { useState, useMemo } from "react";
import { Search, Plus, Clock3, Layers, Satellite, MapPin, Flame } from "lucide-react";
import { useChatStore } from "@/store/chat.store";
import { analyses } from "@/mocks/analyses";
import { relativeTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useWorkspaceStore } from "@/store/workspace.store";

export function LeftSessionsPanel() {
  const [q, setQ] = useState("");
  const { clear } = useChatStore();
  const { activeAnalysisId, setActiveAnalysisId } = useWorkspaceStore();

  const filtered = useMemo(() => {
    if (!q) return analyses;
    const lower = q.toLowerCase();
    return analyses.filter(a => a.title.toLowerCase().includes(lower) || a.category.toLowerCase().includes(lower));
  }, [q]);

  const grouped: Record<string, typeof analyses> = {
    TODAY: filtered.slice(0, 2),
    YESTERDAY: filtered.slice(2, 4),
    EARLIER: filtered.slice(4),
  };

  return (
    <div className="w-full h-full bg-[#0D121F] flex flex-col relative overflow-hidden">
      <div className="p-4 space-y-3">
        <button
          onClick={() => { clear(); setActiveAnalysisId(null); }}
          className="w-full h-10 flex items-center justify-center gap-2 rounded-[10px] bg-gradient-to-r from-[#06B6D4] to-[#06B6D4] text-white text-[14px] font-semibold shadow-sm hover:brightness-110 transition-all"
        >
          <Plus size={16} /> New chat
        </button>
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#64748B]" />
          <input
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Search sessions…"
            aria-label="Search sessions"
            className="w-full h-9 rounded-[10px] bg-[#0D121F] border border-slate-800/60 pl-9 pr-3 text-[13px] text-[#F8FAFC] placeholder:text-[#64748B] outline-none focus:border-[#06B6D4] focus:bg-[#0D121F] transition-colors"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto px-2">
        {Object.entries(grouped).map(([group, items]) =>
          items.length ? (
            <div key={group} className="pb-4">
              <div className="px-3 py-2 text-[11px] font-semibold tracking-[0.06em] text-[#64748B] uppercase">{group}</div>
              <div className="space-y-1">
                {items.map(a => {
                  const active = activeAnalysisId === a.id;
                  return (
                    <button
                      key={a.id}
                      onClick={() => setActiveAnalysisId(a.id)}
                      className={cn(
                        "w-full text-left flex items-start gap-2.5 px-3 py-2.5 rounded-lg transition-colors relative",
                        "h-[52px]",
                        active ? "bg-[#0D121F] text-white" : "text-[#94A3B8] hover:bg-[#0D121F] hover:text-[#F8FAFC] bg-transparent"
                      )}
                    >
                      {active && <span className="absolute left-0 top-2 bottom-2 w-[3px] bg-[#06B6D4] rounded-full" />}
                      <span className="mt-0.5 shrink-0">
                        {(a.category as string) === "change" ? <Layers size={16} className={active ? "text-white" : "text-[#64748B]"} /> : (a.category as string) === "fusion" ? <Satellite size={16} className={active ? "text-white" : "text-[#64748B]"} /> : (a.category as string) === "wildfire" ? <Flame size={16} className={active ? "text-white" : "text-[#64748B]"} /> : <MapPin size={16} className={active ? "text-white" : "text-[#64748B]"} />}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14px] font-medium leading-tight truncate">{a.title}</span>
                        <span className="flex items-center gap-1 text-[12px] text-[#64748B] mt-0.5 truncate">
                          <span className="capitalize">{a.category}</span> · <Clock3 size={10} /> {relativeTime(a.createdAt)}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null
        )}
        {filtered.length === 0 && <div className="px-4 py-6 text-xs text-[#64748B] text-center">No sessions match “{q}”</div>}
      </div>

      <div className="p-3 border-t border-slate-800/60 flex items-center gap-2.5">
        <div className="h-7 w-7 rounded-full bg-[#0D121F] border border-slate-800/60 grid place-items-center text-[#94A3B8]">◍</div>
        <div className="min-w-0">
          <div className="text-xs font-semibold text-[#F8FAFC] leading-none">Satiq OS</div>
          <div className="text-[11px] text-[#64748B]">{analyses.length} sessions · Encrypted</div>
        </div>
        <span className="ml-auto h-2 w-2 rounded-full bg-[#22C55E] animate-pulse" />
      </div>
    </div>
  );
}
