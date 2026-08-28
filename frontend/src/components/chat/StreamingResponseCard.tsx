import { useState, useEffect, memo } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
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
  const bufferedThinking = useTokenBuffer(thinking ?? '', 12);
  const bufferedMarkdown = useTokenBuffer(markdownContent, 14);

  // Auto-collapse thinking 800ms after completion per spec
  useEffect(() => {
    if (!thinkingStreaming && thinking && thinking.length > 0) {
      const t = setTimeout(() => setShowThinking(false), 800);
      return () => clearTimeout(t);
    }
    if (thinkingStreaming) setShowThinking(true);
  }, [thinkingStreaming, thinking]);

  const hasThinking = Boolean(thinking && thinking.length > 0) || thinkingStreaming;

  // --- Sanitize streaming markdown tail: hide incomplete ![ ]( ) / [ ]( ) so "Before / After" doesn't flash as plain text then vanish ---
  const sanitizeStreamingMarkdown = (md: string) => {
    if (!md || !isStreaming) return md;
    // Look for the latest incomplete image or link near the tail (streaming edge)
    let candidateIdx = -1;
    const lastImg = md.lastIndexOf("![");
    if (lastImg !== -1 && md.length - lastImg < 800) {
      const tail = md.slice(lastImg);
      const hasAltClose = tail.includes("](");
      const hasCloseParen = tail.lastIndexOf(")") > tail.indexOf("](");
      const isComplete = hasAltClose && hasCloseParen && /\]\([^\)]*\)/.test(tail);
      if (!isComplete) candidateIdx = lastImg;
    }
    // Last link `[` not part of `![`
    let lastLink = -1;
    for (let i = md.length - 1; i >= 0; i--) {
      if (md[i] === "[" && (i === 0 || md[i - 1] !== "!")) {
        if (md.length - i < 600) lastLink = i;
        break;
      }
    }
    if (lastLink !== -1) {
      const tail = md.slice(lastLink);
      const hasAltClose = tail.includes("](");
      const hasCloseParen = tail.lastIndexOf(")") > tail.indexOf("](");
      const isComplete = hasAltClose && hasCloseParen && /\]\([^\)]*\)/.test(tail);
      if (!isComplete && lastLink > candidateIdx) candidateIdx = lastLink;
    }
    if (candidateIdx !== -1) return md.slice(0, candidateIdx);
    return md;
  };
  const sanitizedMarkdown = sanitizeStreamingMarkdown(bufferedMarkdown);

  return (
    <div className="rounded-xl border-0 bg-transparent overflow-hidden">
      {/* Thinking Accordion — top, collapsible, keeps primary response clean */}
      {hasThinking && (
        <div className="border-b border-slate-800/60 bg-[#090D14]/60">
          <button
            onClick={() => setShowThinking(!showThinking)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs font-mono text-[#94A3B8] hover:bg-[#0D121F]/60 transition-colors"
          >
            <span className="flex items-center gap-2">
              <span className={`w-2 h-2 rounded-full ${thinkingStreaming ? 'bg-[#F59E0B] animate-pulse' : 'bg-[#22C55E]'}`} />
              {thinkingStreaming ? 'Thinking — Qwen 3.5 9B executing pipeline…' : `Thought process (${thinkingSteps?.length ?? '—'} steps)`}
            </span>
            <span className="flex items-center gap-1 text-[11px] text-[#64748B]">
              {showThinking ? <><ChevronUp size={12} /> Hide</> : <><ChevronDown size={12} /> View trace</>}
            </span>
          </button>
          {showThinking && (
            <div className="px-3 py-2.5 bg-[#090D14] border-t border-slate-800/60 text-[13px] leading-relaxed text-[#94A3B8] whitespace-pre-wrap font-mono max-h-[220px] overflow-y-auto">
              {bufferedThinking}
              {thinkingStreaming && <span className="inline-block w-2 h-4 ml-1 bg-[#F59E0B] animate-pulse align-middle" />}
              {thinkingSteps && thinkingSteps.length > 0 && (
                <div className="mt-3 pt-3 border-t border-slate-800/60/60 space-y-1.5">
                  {thinkingSteps.map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-[#F8FAFC]">▸ {s.name}</span>
                      <span className="text-[#64748B] font-mono text-[11px]">{s.duration ? `${s.duration}ms` : s.status ?? ''}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Main content stream — transparent outer, liquid via useTokenBuffer (sanitized tail) */}
      <div className="px-1 py-2">
        <div className="text-[#F8FAFC] text-[14px] leading-relaxed">
          <StreamMarkdown content={sanitizedMarkdown} />
          {isStreaming && <span className="inline-block w-2 h-4 ml-1 bg-[#06B6D4] animate-pulse align-middle" />}
        </div>
      </div>
    </div>
  );
});
