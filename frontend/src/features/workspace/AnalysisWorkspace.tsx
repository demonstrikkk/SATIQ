import { useEffect, lazy, Suspense, useState } from "react";
import { TopCommandBar } from "@/components/shell/TopCommandBar";
import { LeftSessionsPanel } from "@/components/shell/LeftSessionsPanel";
import { RightThinkingPanel } from "@/components/shell/RightThinkingPanel";
import { ChatCanvas } from "@/components/chat/ChatCanvas";
import { useWorkspaceStore } from "@/store/workspace.store";
import { useChatStore } from "@/store/chat.store";
import { useExecutionStore } from "@/store/execution.store";
import { simulateAnalysisQuery } from "@/mocks/mockStream";
import { Skeleton } from "@/components/ui/skeleton";
import { Map as MapIcon, Satellite, X, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";

const GeoCanvas = lazy(() => import("@/components/workspace/GeoCanvas").then(m => ({ default: m.GeoCanvas })));

export function AnalysisWorkspace() {
  const { setCommandOpen, sidebarOpen, inspectorOpen, toggleSidebar, toggleInspector } = useWorkspaceStore();
  const { messages } = useChatStore();
  const { globalStatus } = useExecutionStore();
  const hasConversation = messages.length > 0;
  const [mapOpen, setMapOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (mapOpen) setMapOpen(false);
        else setCommandOpen(false);
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setCommandOpen(true); }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") { e.preventDefault(); toggleSidebar(); }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "i") { e.preventDefault(); toggleInspector(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setCommandOpen, toggleSidebar, toggleInspector, mapOpen]);

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#090D14] text-slate-200 antialiased flex flex-col" style={{ fontFamily: 'Inter, system-ui, sans-serif' }}>
      {/* Top Bar 56px */}
      <div className="h-[56px] shrink-0">
        <TopCommandBar leftOpen={sidebarOpen} rightOpen={inspectorOpen} onToggleLeft={toggleSidebar} onToggleRight={toggleInspector} />
      </div>

      <div className="flex flex-1 min-h-0">
        {/* Left Sidebar — smooth slide with 64px rail, till out when fully closed is still rail (spec) */}
        <motion.div
          className="hidden lg:flex shrink-0 overflow-hidden bg-[#0D121F] border-r border-slate-800/60"
          initial={false}
          animate={{ width: sidebarOpen ? 280 : 64 }}
          transition={{ type: "spring", stiffness: 360, damping: 30 }}
        >
          <AnimatePresence mode="wait" initial={false}>
            {sidebarOpen ? (
              <motion.div
                key="full"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -20, opacity: 0 }}
                transition={{ type: "spring", stiffness: 360, damping: 30 }}
                className="w-[280px] shrink-0 h-full"
              >
                <LeftSessionsPanel />
              </motion.div>
            ) : (
              <motion.div
                key="rail"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -20, opacity: 0 }}
                transition={{ type: "spring", stiffness: 360, damping: 30 }}
                className="w-[64px] shrink-0 h-full flex flex-col items-center py-3 gap-2"
              >
                <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-[#06B6D4] to-[#0891b2] grid place-items-center shadow-md shrink-0">
                  <span className="text-white text-[11px] font-bold">S</span>
                </div>
                <div className="h-px w-8 bg-slate-800/60 my-1" />
                <Button variant="ghost" size="icon" className="h-9 w-9 rounded-xl hover:bg-slate-800/60" onClick={toggleSidebar} aria-label="Conversations — open sidebar">
                  <MessageSquare size={16} />
                </Button>
                <div className="mt-auto flex flex-col items-center gap-2">
                  <div className="h-7 w-7 rounded-full bg-[#0D121F] border border-slate-800/60 grid place-items-center text-slate-400 text-[10px]">◍</div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* Main Chat Area flex-1 — chat only, canvas is now a popup */}
        <div className="flex-1 flex flex-col min-w-0 bg-[#090D14] overflow-hidden relative">
          <div className="flex-1 min-h-0 flex flex-col">
            <ChatCanvas />
          </div>

          {/* Satellite trigger bar — does NOT contain the canvas, just opens popup */}
          {hasConversation && (
            <div className="shrink-0 border-t border-slate-800/60 bg-[#0D121F] h-11 flex items-center justify-between px-4">
              <span className="text-xs font-semibold tracking-[0.08em] text-slate-300 flex items-center gap-2">
                <span className="h-6 w-6 rounded-lg bg-[#0D121F] border border-slate-800/60 grid place-items-center">
                  <MapIcon size={12} className="text-[#60A5FA]" />
                </span>
                SATELLITE CANVAS
                <span className="hidden sm:inline font-normal tracking-normal text-slate-500">— Bengaluru · 7d · EPSG:32617</span>
                <span className="hidden lg:inline-flex ml-2 rounded-full bg-[#22C55E]/10 border border-[#22C55E]/20 px-2 py-0.5 text-[10px] text-[#22C55E]">Ready</span>
              </span>
              <Button size="sm" className="h-7 rounded-full bg-[#06B6D4] text-white hover:bg-[#0891b2] text-xs px-3 gap-1.5" onClick={() => setMapOpen(true)}>
                <Satellite size={12} /> Open map
              </Button>
            </div>
          )}
        </div>

        {/* Right Panel — smooth slide till out (width 360→0 + x 360) */}
        <motion.div
          className="hidden xl:flex shrink-0 overflow-hidden border-l border-slate-800/60 bg-[#0D121F]"
          initial={false}
          animate={{ width: inspectorOpen ? 360 : 0, opacity: inspectorOpen ? 1 : 0 }}
          transition={{ type: "spring", stiffness: 360, damping: 30 }}
        >
          <motion.div
            animate={{ x: inspectorOpen ? 0 : 20, opacity: inspectorOpen ? 1 : 0 }}
            transition={{ type: "spring", stiffness: 360, damping: 30 }}
            className="w-[360px] shrink-0 flex flex-col overflow-hidden h-full"
          >
            <RightThinkingPanel open={inspectorOpen} onClose={toggleInspector} />
          </motion.div>
        </motion.div>
      </div>

      {/* <1024 overlay left */}
      <AnimatePresence>
        {sidebarOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
            onClick={toggleSidebar}
          >
            <motion.div
              initial={{ x: -280 }}
              animate={{ x: 0 }}
              exit={{ x: -280 }}
              transition={{ type: "spring", stiffness: 420, damping: 36 }}
              className="absolute left-0 top-0 bottom-0 w-[280px] bg-[#0D121F] border-r border-slate-800/60 shadow-[0_16px_40px_rgba(0,0,0,0.6)]"
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              <LeftSessionsPanel />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* <1024 overlay right */}
      <AnimatePresence>
        {inspectorOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="xl:hidden fixed inset-0 z-40 bg-black/50 backdrop-blur-sm"
            onClick={toggleInspector}
          >
            <motion.div
              initial={{ x: 360 }}
              animate={{ x: 0 }}
              exit={{ x: 360 }}
              transition={{ type: "spring", stiffness: 420, damping: 36 }}
              className="absolute right-0 top-0 bottom-0 w-[360px] max-w-[86vw] bg-[#0D121F] border-l border-slate-800/60 shadow-[-16px_0_40px_rgba(0,0,0,0.5)] overflow-hidden"
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              <RightThinkingPanel open={true} onClose={toggleInspector} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Satellite Canvas — centered popup modal */}
      <AnimatePresence>
        {mapOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6"
            aria-modal="true"
            role="dialog"
            aria-label="Satellite canvas"
          >
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-black/70 backdrop-blur-sm"
              onClick={() => setMapOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 12 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              className="relative w-full max-w-[1100px] h-[86vh] max-h-[760px] rounded-2xl border border-slate-800/60 bg-[#0D121F] shadow-[0_24px_64px_rgba(0,0,0,0.6)] flex flex-col overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="h-11 shrink-0 flex items-center justify-between px-4 border-b border-slate-800/60 bg-[#090D14]/60">
                <span className="text-xs font-semibold tracking-[0.08em] text-slate-200 flex items-center gap-2">
                  <span className="h-6 w-6 rounded-lg bg-[#0D121F] border border-slate-800/60 grid place-items-center">
                    <MapIcon size={12} className="text-[#60A5FA]" />
                  </span>
                  SATELLITE CANVAS
                  <span className="hidden sm:inline font-normal tracking-normal text-slate-500">— Bengaluru · 7d · EPSG:32617</span>
                </span>
                <Button variant="ghost" size="icon" className="h-7 w-7 rounded-lg bg-[#0D121F] hover:bg-slate-800/60 border border-slate-800/60" onClick={() => setMapOpen(false)} aria-label="Close map">
                  <X size={14} />
                </Button>
              </div>
              <div className="flex-1 min-h-0 overflow-hidden bg-[#090D14]">
                <Suspense fallback={<Skeleton className="h-full w-full rounded-none" />}>
                  <GeoCanvas />
                </Suspense>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <CommandPalette />
    </div>
  );
}

function CommandPalette() {
  const { commandOpen, setCommandOpen } = useWorkspaceStore();
  if (!commandOpen) return null;
  const items = ["Show flood risk areas", "What changed in the last 7 days?", "Detect new construction", "Compare imagery with last month"];
  const { addMessage } = useChatStore.getState();
  return (
    <div className="fixed inset-0 z-50 grid place-items-start pt-[20vh] bg-black/60 backdrop-blur-sm p-4" onClick={() => setCommandOpen(false)} role="dialog" aria-modal="true" aria-label="Command palette">
      <div className="mx-auto w-full max-w-[480px] rounded-2xl border border-slate-800/60 bg-[#0D121F] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200" onClick={e => e.stopPropagation()} style={{ transformOrigin: "50% 20%" }}>
        <div className="px-4 py-3 border-b border-slate-800/60 text-sm text-slate-400 flex items-center gap-2"><Satellite size={14} className="text-[#06B6D4]" /> ⌘K — Ask Satiq</div>
        <div className="p-2">
          {items.map(it => (
            <button key={it} onClick={() => { setCommandOpen(false); addMessage({ id: Date.now().toString(), role: "user", content: it }); simulateAnalysisQuery(it, []); }} className="w-full text-left px-3 py-2.5 rounded-xl text-sm text-slate-400 hover:text-white hover:bg-[#0D121F] transition-colors active:scale-[0.98]">
              {it}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

