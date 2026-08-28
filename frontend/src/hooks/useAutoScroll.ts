import { useEffect, useRef, useCallback, useState } from "react";

/**
 * Custom auto-scroll without layout shift.
 * - Tracks scroll position; pauses if user scrolls >120px from bottom
 * - When pinned, sets scrollTop = scrollHeight instantly (no smooth latency)
 * - Eliminates scrollIntoView() jank on token chunks
 */
export function useAutoScroll(deps: unknown[] = []) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [isPinned, setIsPinned] = useState(true);
  const isPinnedRef = useRef(true);

  const checkPinned = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    const pinned = distanceFromBottom <= 120;
    if (pinned !== isPinnedRef.current) {
      isPinnedRef.current = pinned;
      setIsPinned(pinned);
    }
  }, []);

  const scrollToBottom = useCallback((instant = true) => {
    const el = containerRef.current;
    if (!el || !isPinnedRef.current) return;
    // direct assignment avoids smooth-scroll latency
    if (instant) {
      el.scrollTop = el.scrollHeight;
    } else {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, []);

  const forceScrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return;
    isPinnedRef.current = true;
    setIsPinned(true);
    el.scrollTop = el.scrollHeight;
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const onScroll = () => checkPinned();
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, [checkPinned]);

  // auto-scroll on deps change (token stream)
  useEffect(() => {
    // rAF ensures DOM has painted new content before measuring
    const id = requestAnimationFrame(() => scrollToBottom(true));
    return () => cancelAnimationFrame(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { containerRef, isPinned, scrollToBottom, forceScrollToBottom, checkPinned };
}
