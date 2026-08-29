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
import { Globe, X, MessageSquare, Satellite } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion, AnimatePresence } from "framer-motion";
import { useSessionPersistence } from "@/hooks/useSessionPersistence";

const GeoCanvas = lazy(() =>
  import("@/components/workspace/GeoCanvas").then((m) => ({ default: m.GeoCanvas }))
);

export function AnalysisWorkspace() {
  const { setCommandOpen, sidebarOpen, inspectorOpen, toggleSidebar, toggleInspector } =
    useWorkspaceStore();
  const { messages } = useChatStore();
  const { globalStatus } = useExecutionStore();
  const hasConversation = messages.length > 0;
  const [mapOpen, setMapOpen] = useState(false);

  // persist per-session messages in localStorage (mock, zero API)
  useSessionPersistence();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (mapOpen) setMapOpen(false);
        else setCommandOpen(false);
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen(true);
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "b") {
        e.preventDefault();
        toggleSidebar();
      }
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "i") {
        e.preventDefault();
        toggleInspector();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setCommandOpen, toggleSidebar, toggleInspector, mapOpen]);

  return (
    <div
      className="h-screen w-screen overflow-hidden text-slate-200 antialiased flex flex-col"
      style={{ background: "#05080F", fontFamily: "Inter, system-ui, sans-serif" }}
    >
      {/* Top Bar 56px */}
      <div className="h-[56px] shrink-0">
        <TopCommandBar
          leftOpen={sidebarOpen}
          rightOpen={inspectorOpen}
          onToggleLeft={toggleSidebar}
          onToggleRight={toggleInspector}
        />
      </div>

      <div className="flex flex-1 min-h-0">
        {/* ── Left Sidebar ── smooth slide, 64px rail when collapsed */}
        <motion.div
          className="hidden lg:flex shrink-0 overflow-hidden bg-[#0B1120] border-r border-slate-800/50"
          initial={false}
          animate={{ width: sidebarOpen ? 272 : 60 }}
          transition={{ type: "spring", stiffness: 380, damping: 32 }}
        >
          <AnimatePresence mode="wait" initial={false}>
            {sidebarOpen ? (
              <motion.div
                key="full"
                initial={{ x: -16, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -16, opacity: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
                className="w-[272px] shrink-0 h-full"
              >
                <LeftSessionsPanel />
              </motion.div>
            ) : (
              <motion.div
                key="rail"
                initial={{ x: -16, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -16, opacity: 0 }}
                transition={{ type: "spring", stiffness: 380, damping: 32 }}
                className="w-[60px] shrink-0 h-full flex flex-col items-center py-3 gap-2.5"
              >
                {/* Mini brand mark */}
                <div className="h-8 w-8 rounded-lg bg-[#101827] border border-slate-700/40 grid place-items-center shrink-0">
                  <svg width="18" height="18" viewBox="0 0 28 28" fill="none">
                    <circle cx="14" cy="14" r="12.5" stroke="#334155" strokeWidth="1.25" />
                    <path d="M14 4 A10 10 0 0 1 24 14" stroke="#06B6D4" strokeWidth="1.5" strokeLinecap="round" opacity="0.9" />
                    <circle cx="14" cy="14" r="2.5" fill="#06B6D4" />
                  </svg>
                </div>
                <div className="h-px w-8 bg-slate-800/60 my-0.5" />
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-9 w-9 rounded-xl hover:bg-[#101827] text-slate-500 hover:text-slate-300 transition-colors"
                  onClick={toggleSidebar}
                  aria-label="Open sidebar"
                >
                  <MessageSquare size={15} />
                </Button>
                <div className="mt-auto flex flex-col items-center gap-2">
                  <div className="h-7 w-7 rounded-full bg-[#101827] border border-slate-700/40 grid place-items-center">
                    <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                      <circle cx="7" cy="7" r="5.5" stroke="#334155" strokeWidth="1" />
                      <circle cx="7" cy="7" r="2" fill="#06B6D4" opacity="0.5" />
                    </svg>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>

        {/* ── Main Chat Area ──────────────────────────────────────────── */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden relative" style={{ background: "#05080F" }}>
          <div className="flex-1 min-h-0 flex flex-col">
            <ChatCanvas />
          </div>

          {/* Satellite canvas trigger bar */}
          {hasConversation && (
            <div className="shrink-0 border-t border-slate-800/50 bg-[#0B1120] h-10 flex items-center justify-between px-4">
              <span className="text-[11px] font-semibold tracking-[0.07em] text-slate-400 flex items-center gap-2 uppercase">
                <span className="h-5 w-5 rounded-md bg-[#101827] border border-slate-700/40 grid place-items-center">
                  <Globe size={11} className="text-[#06B6D4]" />
                </span>
                Satellite Canvas
                <span className="hidden sm:inline font-normal tracking-normal normal-case text-slate-600">
                  — Bengaluru · 7d · EPSG:32617
                </span>
                <span className="hidden lg:inline-flex ml-1 rounded-full bg-[#22C55E]/8 border border-[#22C55E]/15 px-2 py-0.5 text-[10px] text-[#22C55E] font-medium normal-case tracking-normal">
                  Ready
                </span>
              </span>
              <Button
                size="sm"
                className="h-6 rounded-full bg-[#101827] border border-slate-700/40 text-slate-300 hover:bg-[#141F30] hover:text-slate-100 hover:border-slate-600/50 text-[11px] px-3 gap-1.5 shadow-none"
                onClick={() => setMapOpen(true)}
              >
                <Satellite size={11} />
                Open map
              </Button>
            </div>
          )}
        </div>

        {/* ── Right Thinking Panel ─────────────────────────────────────── */}
        <motion.div
          className="hidden xl:flex shrink-0 overflow-hidden border-l border-slate-800/50 bg-[#0B1120]"
          initial={false}
          animate={{ width: inspectorOpen ? 360 : 0, opacity: inspectorOpen ? 1 : 0 }}
          transition={{ type: "spring", stiffness: 380, damping: 32 }}
        >
          <motion.div
            animate={{ x: inspectorOpen ? 0 : 16, opacity: inspectorOpen ? 1 : 0 }}
            transition={{ type: "spring", stiffness: 380, damping: 32 }}
            className="w-[360px] shrink-0 flex flex-col overflow-hidden h-full"
          >
            <RightThinkingPanel open={inspectorOpen} onClose={toggleInspector} />
          </motion.div>
        </motion.div>
      </div>

      {/* ── Mobile overlays ────────────────────────────────────────────── */}
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
              initial={{ x: -272 }}
              animate={{ x: 0 }}
              exit={{ x: -272 }}
              transition={{ type: "spring", stiffness: 420, damping: 36 }}
              className="absolute left-0 top-0 bottom-0 w-[272px] bg-[#0B1120] border-r border-slate-800/50 shadow-[16px_0_40px_rgba(0,0,0,0.5)]"
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              <LeftSessionsPanel />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
              className="absolute right-0 top-0 bottom-0 w-[360px] max-w-[88vw] bg-[#0B1120] border-l border-slate-800/50 shadow-[-16px_0_40px_rgba(0,0,0,0.5)] overflow-hidden"
              onClick={(e: React.MouseEvent) => e.stopPropagation()}
            >
              <RightThinkingPanel open={true} onClose={toggleInspector} />
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Satellite Canvas Modal ──────────────────────────────────────── */}
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
              className="absolute inset-0 bg-black/75 backdrop-blur-md"
              onClick={() => setMapOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.97, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97, y: 10 }}
              transition={{ type: "spring", stiffness: 380, damping: 32 }}
              className="relative w-full max-w-[1100px] h-[88vh] max-h-[760px] rounded-2xl border border-slate-700/50 bg-[#0B1120] shadow-[0_24px_64px_rgba(0,0,0,0.7)] flex flex-col overflow-hidden"
              onClick={(e) => e.stopPropagation()}
            >
              {/* Map header */}
              <div className="h-10 shrink-0 flex items-center justify-between px-4 border-b border-slate-800/50 bg-[#05080F]/60">
                <span className="text-[11px] font-semibold tracking-[0.07em] text-slate-300 flex items-center gap-2 uppercase">
                  <span className="h-5 w-5 rounded-md bg-[#101827] border border-slate-700/40 grid place-items-center">
                    <Globe size={11} className="text-[#06B6D4]" />
                  </span>
                  Satellite Canvas
                  <span className="hidden sm:inline font-normal tracking-normal normal-case text-slate-500">
                    — Bengaluru · 7d · EPSG:32617
                  </span>
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 rounded-lg bg-[#101827] hover:bg-[#141F30] border border-slate-700/40 text-slate-400 hover:text-slate-200"
                  onClick={() => setMapOpen(false)}
                  aria-label="Close map"
                >
                  <X size={13} />
                </Button>
              </div>

              {/* Map canvas */}
              <div className="flex-1 min-h-0 overflow-hidden bg-[#05080F]">
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

  const items = [
    "Show flood risk areas",
    "What changed in the last 7 days?",
    "Detect new construction",
    "Compare imagery with last month",
  ];
  const { addMessage } = useChatStore.getState();

  return (
    <div
      className="fixed inset-0 z-50 grid place-items-start pt-[18vh] bg-black/65 backdrop-blur-sm p-4"
      onClick={() => setCommandOpen(false)}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="mx-auto w-full max-w-[480px] rounded-2xl border border-slate-700/50 bg-[#0B1120] shadow-[0_24px_64px_rgba(0,0,0,0.7)] overflow-hidden animate-in fade-in zoom-in-95 duration-200"
        onClick={(e) => e.stopPropagation()}
        style={{ transformOrigin: "50% 20%" }}
      >
        {/* Palette header */}
        <div className="px-4 py-3 border-b border-slate-800/50 flex items-center gap-2">
          <svg width="14" height="14" viewBox="0 0 28 28" fill="none" className="shrink-0">
            <circle cx="14" cy="14" r="12.5" stroke="#334155" strokeWidth="1.25" />
            <path d="M14 4 A10 10 0 0 1 24 14" stroke="#06B6D4" strokeWidth="1.5" strokeLinecap="round" />
            <circle cx="14" cy="14" r="2.5" fill="#06B6D4" />
          </svg>
          <span className="text-[12px] text-slate-400">⌘K — Ask Satiq about Earth</span>
        </div>
        <div className="p-1.5">
          {items.map((it) => (
            <button
              key={it}
              onClick={() => {
                setCommandOpen(false);
                addMessage({ id: Date.now().toString(), role: "user", content: it });
                simulateAnalysisQuery(it, []);
              }}
              className="w-full text-left px-3 py-2.5 rounded-xl text-[13px] text-slate-400 hover:text-white hover:bg-[#141F30] transition-colors active:scale-[0.98]"
            >
              {it}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
