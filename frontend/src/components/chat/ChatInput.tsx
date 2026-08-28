import { Composer } from "./Composer";

/**
 * Docked input container per spec:
 * p-4 bg-[#090D14]/80 backdrop-blur border-t border-slate-800/40
 */
export function ChatInput() {
  return (
    <div className="p-4 bg-[#090D14]/80 backdrop-blur border-t border-slate-800/40 shrink-0">
      <Composer />
    </div>
  );
}
