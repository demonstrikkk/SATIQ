/**
 * Real gateway client — agentic pipeline via gateway → orchestrator.
 * Uses gateway POST /api/query + SSE, updates stores via applyExecutionEvent.
 * Falls back to caller handling if gateway unreachable.
 */
import type { ExecutionEvent } from "@/schemas/execution";
import { applyExecutionEvent, resetLastAssistantId } from "./applyEvent";

const GATEWAY = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "") || "";
const TOKEN_KEY = "satiq_token";

async function ensureAuth(): Promise<string | null> {
  const existing = localStorage.getItem(TOKEN_KEY);
  if (existing) return existing;
  try {
    const res = await fetch(`${GATEWAY}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { token: string };
    if (data.token) {
      localStorage.setItem(TOKEN_KEY, data.token);
      return data.token;
    }
  } catch {
    return null;
  }
  return null;
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
  const asset_ids = contexts.filter((c) => c.type === "image").map((c) => c.id);
  const spatial_refs = contexts.filter((c) => c.type === "aoi").map((c) => c.label);

  let tok = await ensureAuth();
  let res = await fetch(`${GATEWAY}/api/query`, {
    method: "POST",
    headers: authHeaders(tok),
    body: JSON.stringify({ query, asset_ids: asset_ids.length ? asset_ids : undefined, spatial_refs: spatial_refs.length ? spatial_refs : undefined }),
    signal,
  });
  if (res.status === 401) {
    localStorage.removeItem(TOKEN_KEY);
    tok = await ensureAuth();
    res = await fetch(`${GATEWAY}/api/query`, {
      method: "POST",
      headers: authHeaders(tok),
      body: JSON.stringify({ query, asset_ids: asset_ids.length ? asset_ids : undefined, spatial_refs: spatial_refs.length ? spatial_refs : undefined }),
      signal,
    });
  }
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    const msg = `POST /api/query ${res.status}: ${txt.slice(0, 300)}`;
    applyExecutionEvent({ event: "error", payload: { message: msg } });
    throw new Error(msg);
  }
  const { execution_id } = (await res.json()) as { execution_id: string };
  if (!execution_id) throw new Error("No execution_id");

  resetLastAssistantId();
  const streamUrl = `${GATEWAY}/api/query/${encodeURIComponent(execution_id)}/stream`;
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  const tok2 = localStorage.getItem(TOKEN_KEY);
  if (tok2) headers["Authorization"] = `Bearer ${tok2}`;

  const resp = await fetch(streamUrl, { headers, signal });
  if (!resp.ok || !resp.body) {
    const msg = `SSE ${resp.status}`;
    applyExecutionEvent({ event: "error", payload: { message: msg } });
    throw new Error(msg);
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
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
        applyExecutionEvent(ev);
      } catch {
        applyExecutionEvent({ event: (eventName as any) ?? "answer_delta", payload: { chunk: dataLine } });
      }
    }
    if (signal?.aborted) break;
  }
}
