import { useState, useEffect, useRef } from 'react';

/**
 * Satiq-adapted token buffer: decouples irregular SSE chunks from DOM renders.
 * For SatQuery, network delivers Qwen 3.5 9B tokens + model JSON + bbox RLE in bursts.
 * We unveil 1-3 chars per frame via rAF @ ~15ms for liquid typing without jitter.
 */
export function useTokenBuffer(rawText: string, speedMs = 15) {
  const [displayedText, setDisplayedText] = useState('');
  const targetRef = useRef(rawText);
  const rafRef = useRef<number | null>(null);
  const lastTickRef = useRef(performance.now());

  targetRef.current = rawText;

  // Reset when rawText is reset (new message)
  useEffect(() => {
    if (rawText.length === 0) setDisplayedText('');
  }, [rawText]);

  useEffect(() => {
    const tick = (now: number) => {
      if (now - lastTickRef.current >= speedMs) {
        lastTickRef.current = now;
        setDisplayedText(prev => {
          if (prev.length < targetRef.current.length) {
            const remain = targetRef.current.length - prev.length;
            // adapt speed: faster for long bursts, slower for thinking
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
  }, [speedMs]);

  // If raw is shorter (reset), snap
  useEffect(() => {
    if (targetRef.current.length < displayedText.length) {
      setDisplayedText(targetRef.current);
    }
  }, [rawText, displayedText.length]);

  return displayedText;
}
