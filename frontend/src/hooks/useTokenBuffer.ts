import { useState, useEffect, useRef } from 'react';

/**
 * Satiq-adapted token buffer: decouples irregular SSE chunks from DOM renders.
 * For SatQuery, network delivers Qwen 3.5 9B tokens + model JSON + bbox RLE in bursts.
 * We unveil 1-3 chars per frame via rAF @ ~15ms for liquid typing without jitter.
 */
/**
 * DURABILITY INVARIANT — SCROLL/TYPEWRITER MUST NOT REGRESS:
 * - When a session is reopened or tab is revisited, already-streamed text must NOT re-type from 0.
 * - Initialize displayedText to rawText (not ''), animate only the delta as rawText grows.
 * - When enabled=false (completed/restored message), snap instantly.
 * Future edits: do not change initial state to '' when enabled=true — that causes replay bug.
 */
export function useTokenBuffer(rawText: string, speedMs = 15, enabled = true) {
  const [displayedText, setDisplayedText] = useState(() => rawText);
  const targetRef = useRef(rawText);
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef(performance.now());
  const enabledRef = useRef(enabled);

  targetRef.current = rawText;
  enabledRef.current = enabled;

  // When disabled -> instantly show rawText (no typewriter on replay / tab switch / session restore)
  useEffect(() => {
    if (!enabled) {
      setDisplayedText(rawText);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      return;
    }
    // enabled and rawText was reset to empty (new message) -> reset displayed
    if (rawText.length === 0) setDisplayedText('');
  }, [rawText, enabled]);

  useEffect(() => {
    if (!enabled) return;
    const tick = (now: number) => {
      if (!enabledRef.current) return;
      if (now - lastTickRef.current >= speedMs) {
        lastTickRef.current = now;
        setDisplayedText(prev => {
          if (prev.length < targetRef.current.length) {
            const remain = targetRef.current.length - prev.length;
            const inc = Math.min(remain <= 20 ? 1 : 3, remain);
            return targetRef.current.slice(0, prev.length + inc);
          }
          return prev;
        });
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [speedMs, enabled]);

  // If raw is shorter (reset), snap
  useEffect(() => {
    if (targetRef.current.length < displayedText.length) {
      setDisplayedText(targetRef.current);
    }
  }, [rawText, displayedText.length]);

  // Direct return when disabled
  if (!enabled) return rawText;

  return displayedText;
}
