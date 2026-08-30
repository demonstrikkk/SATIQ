import React, { useEffect } from "react";
import { ensureToken } from "@/lib/auth";
import { useWorkspaceStore } from "@/store/workspace.store";

/**
 * Non-visual bootstrap: transparently mints a JWT (we are the only user) and
 * pulls canonical sessions from the backend. Replaces a visible login screen.
 */
export function Bootstrap({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const tok = await ensureToken();
      if (!cancelled && tok) {
        await useWorkspaceStore.getState().initSessions();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  return <>{children}</>;
}
