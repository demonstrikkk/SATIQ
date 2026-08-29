import { useState, useEffect, memo } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { StreamMarkdown } from './StreamMarkdown';
import { useTokenBuffer } from '@/hooks/useTokenBuffer';

type ThinkingStep = { name: string; duration?: number; status?: 'pending'|'running'|'completed' };

export const StreamingResponseCard = memo(function StreamingResponseCard({
  thinking,
  thinkingStreaming,
  markdownContent,
  isStreaming,
  thinkingSteps,
}: {
  thinking?: string;
  thinkingStreaming?: boolean;
  markdownContent: string;
  isStreaming?: boolean;
  thinkingSteps?: ThinkingStep[];
}) {
  const [showThinking, setShowThinking] = useState(true);
  const [keepOpen, setKeepOpen] = useState(false);
  const [startedAt] = useState(() => Date.now());
  const [now, setNow] = useState(Date.now());
  // Only typewriter while streaming; completed messages / restored sessions render instantly (no replay on tab switch)
  const bufferedThinking = useTokenBuffer(thinking ?? '', 12, !!thinkingStreaming);
  const bufferedMarkdown = useTokenBuffer(markdownContent, 14, !!isStreaming);

  useEffect(() => {
    if (!thinkingStreaming) return;
    const id = setInterval(() => setNow(Date.now()), 120);
    return () => clearInterval(id);
  }, [thinkingStreaming]);

  // Auto-collapse thinking 800ms after completion per spec, unless user kept open
  useEffect(() => {
    if (!thinkingStreaming && thinking && thinking.length > 0) {
      if (keepOpen) return;
      const t = setTimeout(() => setShowThinking(false), 800);
      return () => clearTimeout(t);
    }
    if (thinkingStreaming) {
      if (!keepOpen) setShowThinking(true);
    }
  }, [thinkingStreaming, thinking, keepOpen]);

  const hasThinking = Boolean(thinking && thinking.length > 0) || thinkingStreaming;

  // B1: robust tail sanitization — hide incomplete ![ ]( ), [ ]( ), ``` fences and chart blocks to avoid flash
  const sanitizeStreamingMarkdown = (md: string) => {
    if (!md || !isStreaming) return md;
    let cut = -1;
    const fences = (md.match(/```/g) || []).length;
    if (fences % 2 === 1) {
      const lastFence = md.lastIndexOf("```");
      // incomplete chart/code block at tail — hide from fence start
      if (md.length - lastFence < 1200) cut = Math.max(cut, lastFence);
    }
    // incomplete image ![...](...)
    const lastImg = md.lastIndexOf("![");
    if (lastImg !== -1 && md.length - lastImg < 900) {
      const tail = md.slice(lastImg);
      const hasAltClose = tail.includes("](");
      const hasCloseParen = tail.lastIndexOf(")") > tail.indexOf("](");
      const isComplete = hasAltClose && hasCloseParen && /\]\([^\)]*\)/.test(tail);
      if (!isComplete) cut = Math.max(cut, lastImg);
    }
    // Last link `[` not part of `![`
    let lastLink = -1;
    for (let i = md.length - 1; i >= 0; i--) {
      if (md[i] === "[" && (i === 0 || md[i - 1] !== "!")) {
        if (md.length - i < 650) lastLink = i;
        break;
      }
    }
    if (lastLink !== -1) {
      const tail = md.slice(lastLink);
      const hasAltClose = tail.includes("](");
      const hasCloseParen = tail.lastIndexOf(")") > tail.indexOf("](");
      const isComplete = hasAltClose && hasCloseParen && /\]\([^\)]*\)/.test(tail);
      if (!isComplete) cut = Math.max(cut, lastLink);
    }
    // incomplete bbox token [[bbox:
    const lastBbox = md.lastIndexOf("[[bbox:");
    if (lastBbox !== -1 && md.length - lastBbox < 300) {
      const tail = md.slice(lastBbox);
      if (!tail.includes("]]")) cut = Math.max(cut, lastBbox);
    }
    if (cut !== -1) return md.slice(0, cut);
    return md;
  };
  const sanitizedMarkdown = sanitizeStreamingMarkdown(bufferedMarkdown);

  return (
    <div className="overflow-hidden">
      {/* Thinking Accordion — html .trace-box style: border + surface, max 340 */}
      {hasThinking && (
        <div className="mb-3 rounded-[8px] border border-slate-700/40 bg-[#121615] overflow-hidden max-w-[340px]">
          <button
            onClick={() => {
              const next = !showThinking;
              setShowThinking(next);
              setKeepOpen(next);
            }}
            className="w-full flex items-center justify-between px-3.5 py-2.5 text-xs font-mono text-slate-400 hover:bg-[#181d1b] transition-colors"
            aria-expanded={showThinking}
          >
            <span className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full shrink-0 ${thinkingStreaming ? 'bg-[#F59E0B] animate-pulse' : 'bg-[#22C55E]'}`} style={thinkingStreaming ? { boxShadow: "0 0 6px rgba(245,158,11,0.5)" } : { boxShadow: "0 0 6px rgba(34,197,94,0.5)" }} />
              {thinkingStreaming ? `Thinking — Qwen 3.5 9B… ${Math.round((now - startedAt)/100)/10}s · ${bufferedThinking.length} chars` : `Thought process (${thinkingSteps?.length ?? '—'} steps) · ${bufferedThinking.length} chars`}
            </span>
            <span className="flex items-center gap-1 text-[11px] text-slate-500 font-medium">
              {showThinking ? <><ChevronUp size={12} /> Hide</> : <><ChevronDown size={12} /> View trace</>}
            </span>
          </button>
          <AnimatePresence initial={false}>
            {showThinking && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden border-t border-slate-700/30"
              >
                <div className="px-3.5 py-3 bg-[#05080F] text-[12.5px] leading-relaxed text-slate-400 whitespace-pre-wrap font-mono max-h-[220px] overflow-y-auto">
                  {bufferedThinking}
                  {thinkingStreaming && <span className="inline-block w-2 h-4 ml-1 bg-[#F59E0B] animate-pulse align-middle" />}
                  {thinkingSteps && thinkingSteps.length > 0 && (
                    <div className="mt-3 pt-3 border-t border-slate-800/40 space-y-1.5">
                      {thinkingSteps.map((s, i) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="text-slate-200">▸ {s.name}</span>
                          <span className="text-slate-500 font-mono text-[11px]">{s.duration ? `${s.duration}ms` : s.status ?? ''}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      )}

      {/* Main content — html .msg-text: no card, transparent, 14/1.65 */}
      <div className="text-slate-100 text-[14px] leading-[1.65]">
        <StreamMarkdown content={sanitizedMarkdown} />
        {isStreaming && <span className="inline-block w-2 h-4 ml-1 bg-[#06B6D4] animate-pulse align-middle" />}
      </div>
    </div>
  );
});
