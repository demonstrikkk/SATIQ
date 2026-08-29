import { useEffect, useRef, useCallback, useState } from "react";

/**
 * DURABILITY INVARIANT — AUTO-SCROLL MUST RESPECT USER INTENT:
 * - Auto-scroll ONLY when isPinned (distanceFromBottom <= 120). If user scrolls up >120px, NEVER force scroll on new tokens.
 * - New tokens must NOT re-enable auto-scroll; only user clicking "Scroll to bottom" (forceScrollToBottom) re-pins.
 * - forceScrollToBottom is the manual override — it sets isPinned=true and smooth-scrolls. Do not call it from auto effects.
 * - Do not add scroll-smooth CSS to the container; instant scrollTop is required for streaming, smooth only for force.
 * Future edits: keep 120px threshold, keep isPinnedRef guard in scrollToBottom, keep force as only re-pin.
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
    // Smooth for user-initiated override, instant for auto
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
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
