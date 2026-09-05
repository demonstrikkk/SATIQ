/**
 * Real gateway client — agentic pipeline via gateway → orchestrator.
 * Production: consumeSSE via fetch SSE, all event types, Abort→cancel.
 * Mock behind flag: VITE_USE_MOCK=true or VITE_USE_MOCKS=true (dev).
 */
import type { ExecutionEvent } from "@/schemas/execution";
import { applyExecutionEvent, resetLastAssistantId } from "./applyEvent";
import { simulateAnalysisQuery } from "@/mocks/mockStream";
import { ensureToken } from "@/lib/auth";

const GATEWAY = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "") || "";
const TOKEN_KEY = "satiq_token";
const USE_MOCK = (import.meta as any).env?.VITE_USE_MOCK === "true" || (import.meta as any).env?.VITE_USE_MOCKS === "true";

let currentAbort: AbortController | null = null;
let currentExecutionId: string | null = null;
export function getCurrentExecutionId() { return currentExecutionId; }
export async function cancelCurrentAnalysis(): Promise<boolean> {
  const eid = currentExecutionId;
  if (currentAbort) try { currentAbort.abort(); } catch {}
  if (!eid) return false;
  try {
    const tok = localStorage.getItem(TOKEN_KEY);
    const headers: Record<string, string> = {};
    if (tok) headers["Authorization"] = `Bearer ${tok}`;
    const res = await fetch(`${GATEWAY}/api/query/${encodeURIComponent(eid)}/cancel`, { method: "POST", headers });
    return res.ok;
  } catch {
    return false;
  } finally {
    currentExecutionId = null;
    currentAbort = null;
  }
}

async function ensureAuth(): Promise<string | null> {
  return ensureToken();
}

function authHeaders(token: string | null): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json", Accept: "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  return h;
}

export async function executeRealAnalysis(
  query: string,
  contexts: Array<{ id: string; type: string; label: string; preview?: string }>,
  signal?: AbortSignal
): Promise<void> {
  if (USE_MOCK) {
    await simulateAnalysisQuery(query, contexts as any);
    return;
  }
  const asset_ids = contexts.filter((c) => c.type === "image").map((c) => c.id);
  const spatial_refs = contexts.filter((c) => c.type === "aoi").map((c) => c.label);
  const abort = signal ? null : new AbortController();
  const effectiveSignal = signal ?? abort!.signal;
  if (abort) currentAbort = abort;
  else if (signal) {
    // propagate external abort to internal tracking without no-op
    const ctrl = new AbortController();
    const onAbort = () => ctrl.abort();
    signal.addEventListener('abort', onAbort, { once: true });
    currentAbort = ctrl;
  }

  let tok = await ensureAuth();
  let res = await fetch(`${GATEWAY}/api/query`, {
    method: "POST",
    headers: authHeaders(tok),
    body: JSON.stringify({ query, asset_ids: asset_ids.length ? asset_ids : undefined, spatial_refs: spatial_refs.length ? spatial_refs : undefined }),
    signal: effectiveSignal,
  });
  // 401 or 403 both mean token invalid/expired or session belongs to old user.
  // For single-user dev, auto-heal: clear stale token, re-login with deterministic userId, retry once.
  if (res.status === 401 || res.status === 403) {
    localStorage.removeItem(TOKEN_KEY);
    tok = await ensureAuth();
    res = await fetch(`${GATEWAY}/api/query`, {
      method: "POST",
      headers: authHeaders(tok),
      body: JSON.stringify({ query, asset_ids: asset_ids.length ? asset_ids : undefined, spatial_refs: spatial_refs.length ? spatial_refs : undefined }),
      signal: effectiveSignal,
    });
  }
  if (res.status === 401 || res.status === 403) {
    // Token still rejected after re-login → surface a login prompt. Best-effort.
    try { window.dispatchEvent(new CustomEvent("satiq:auth-required", { detail: { reason: "invalid_token" } })); } catch {}
  }
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    let msg = `POST /api/query ${res.status}: ${txt.slice(0, 300)}`;
    if (txt.includes("MODEL_NOT_LINKED") || txt.includes("MODEL_LOAD_ERROR")) {
      msg = `MODEL_NOT_LINKED: Model weights not mounted. Run: python scripts/download_weights.py --model all && docker compose up --build — ${txt.slice(0,150)}`;
      applyExecutionEvent({ event: "error", payload: { message: msg, code: "MODEL_NOT_LINKED" } });
    } else if (res.status === 503 || txt.includes("VRAM_QUEUE_FULL") || txt.includes("queue_full")) {
      msg = `GPU busy (503) — queue full, retry in 6s. ${txt.slice(0,120)}`;
      applyExecutionEvent({ event: "error", payload: { message: msg, code: "queue_full" } });
    } else if (res.status === 403) msg = `Access denied (403) — session belongs to another user. ${txt.slice(0,120)}`;
    else if (res.status === 429) msg = `Rate limited (429) — too many requests. ${txt.slice(0,120)}`;
    else if (res.status === 400) msg = `Validation failed (400): ${txt.slice(0,200)}`;
    if (!msg.includes("MODEL_NOT_LINKED") && !msg.includes("queue_full")) applyExecutionEvent({ event: "error", payload: { message: msg, code: String(res.status) } });
    currentExecutionId = null; currentAbort = null;
    throw new Error(msg);
  }
  const { execution_id } = (await res.json()) as { execution_id: string };
  if (!execution_id) throw new Error("No execution_id");
  currentExecutionId = execution_id;
  resetLastAssistantId();
  const streamUrl = `${GATEWAY}/api/query/${encodeURIComponent(execution_id)}/stream`;
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const tok2 = localStorage.getItem(TOKEN_KEY);
  if (tok2) headers["Authorization"] = `Bearer ${tok2}`;

  let resp: Response;
  try {
    resp = await fetch(streamUrl, { headers, signal: effectiveSignal });
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      applyExecutionEvent({ event: "cancelled", payload: { reason: "cancelled_by_user" } });
      currentExecutionId = null; currentAbort = null;
      return;
    }
    applyExecutionEvent({ event: "error", payload: { message: `Network error: ${(e as Error).message}`, code: "network" } });
    throw e;
  }
  if (!resp.ok || !resp.body) {
    const msg = `SSE ${resp.status}`;
    applyExecutionEvent({ event: "error", payload: { message: msg } });
    currentExecutionId = null; currentAbort = null;
    throw new Error(msg);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parts = buf.split("\n\n");
      buf = parts.pop() ?? "";
      for (const part of parts) {
        let eventName: string | null = null;
        let dataLine: string | null = null;
        for (const line of part.split("\n")) {
          const t = line.trim();
          if (t.startsWith("event:")) eventName = t.slice(6).trim();
          else if (t.startsWith("data:")) dataLine = t.slice(5).trim();
        }
        if (!dataLine) continue;
        try {
          const obj = JSON.parse(dataLine);
          const ev: ExecutionEvent = {
            event: (eventName as any) ?? (obj.event as any) ?? "answer_delta",
            payload: obj.payload ?? (obj.event ? obj.payload : obj),
            timestamp: obj.timestamp ?? Date.now(),
          };
          if (!obj.event && eventName) {
            ev.event = eventName as any;
            ev.payload = obj;
          }
          // Handle all real types: thinking_delta/done, answer_delta/final, model_progress, evidence_*, composer_*, error/cancelled
          applyExecutionEvent(ev);
          if (ev.event === "error" || ev.event === "cancelled") {
            // terminal — stop loop
            if (ev.event === "cancelled") { currentExecutionId = null; currentAbort = null; return; }
          }
        } catch {
          applyExecutionEvent({ event: (eventName as any) ?? "answer_delta", payload: { chunk: dataLine } });
        }
      }
      if (effectiveSignal.aborted) {
        applyExecutionEvent({ event: "cancelled", payload: { reason: "cancelled_by_user" } });
        break;
      }
    }
  } catch (e) {
    if ((e as Error).name === "AbortError") {
      applyExecutionEvent({ event: "cancelled", payload: { reason: "cancelled_by_user" } });
    } else {
      applyExecutionEvent({ event: "error", payload: { message: `Stream error: ${(e as Error).message}`, code: "network" } });
      throw e;
    }
  } finally {
    // Only force completed if not already failed/cancelled — do not mask failures
    try {
      const { useChatStore } = await import("@/store/chat.store");
      const { useExecutionStore } = await import("@/store/execution.store");
      const exec = useExecutionStore.getState();
      const gs = exec.globalStatus;
      const isBusy = ["queued","planning","executing","aggregating","composing"].includes(gs as any);
      const isTerminalFailed = (gs as any) === "failed" || (gs as any) === "cancelled";
      if (isBusy && !isTerminalFailed) {
        const msgs = useChatStore.getState().messages;
        const lastStreaming = msgs.find(m => m.role === "assistant" && (m as any).streaming);
        if (lastStreaming) {
          useChatStore.getState().setStreaming(lastStreaming.id, false);
          useChatStore.getState().setThinkingStreaming(lastStreaming.id, false);
        }
        const lastThinking = msgs.find(m => m.role === "assistant" && (m as any).thinkingStreaming);
        if (lastThinking) {
          useChatStore.getState().setThinkingStreaming(lastThinking.id, false);
        }
        const hasContent = msgs.some(m => m.role === "assistant" && m.content.length > 0);
        if (hasContent || gs !== "idle") {
          useExecutionStore.getState().setGlobalStatus("completed" as any);
          useExecutionStore.getState().setComposerStatus("completed" as any);
        }
      }
    } catch {}
    currentExecutionId = null;
    currentAbort = null;
  }
}
