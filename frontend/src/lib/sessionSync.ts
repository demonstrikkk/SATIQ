/**
 * Backend session sync — mirrors the local workspace sessions to the gateway's
 * authenticated /api/session store. All calls are best-effort: failures are
 * swallowed so the app keeps working on localStorage alone (offline / no token).
 */
import type { PersistedSession } from "@/store/workspace.store";

const TOKEN_KEY = "satiq_token";

export interface BackendSession {
  sessionId: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  metadata?: { category?: string; [k: string]: unknown };
  chatHistory?: unknown[];
}

function token(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function baseUrl(): string {
  return (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "") || "";
}

function headers(extra?: Record<string, string>): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const t = token();
  if (t) h["Authorization"] = `Bearer ${t}`;
  return { ...h, ...(extra ?? {}) };
}

export function toBackend(s: PersistedSession): { name: string; metadata: Record<string, unknown>; sessionId?: string } {
  return {
    sessionId: s.id,
    name: s.title,
    metadata: { category: s.category },
  };
}

export function fromBackend(b: BackendSession): PersistedSession {
  return {
    id: b.sessionId,
    title: b.name,
    category: (b.metadata?.category as PersistedSession["category"]) ?? "vqa",
    createdAt: b.createdAt,
    updatedAt: b.updatedAt,
  };
}

export async function fetchSessions(): Promise<PersistedSession[] | null> {
  if (!token()) return null;
  try {
    const res = await fetch(`${baseUrl()}/api/session`, { headers: headers() });
    if (!res.ok) return null;
    const data = (await res.json()) as BackendSession[];
    if (!Array.isArray(data)) return null;
    return data.map(fromBackend);
  } catch {
    return null;
  }
}

export async function createSessionBackend(s: PersistedSession): Promise<boolean> {
  if (!token()) return false;
  try {
    const res = await fetch(`${baseUrl()}/api/session`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(toBackend(s)),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function updateSessionBackend(
  id: string,
  patch: { name?: string; category?: string; chatHistory?: unknown[] }
): Promise<boolean> {
  if (!token()) return false;
  try {
    const body: Record<string, unknown> = {};
    if (patch.name !== undefined) body.name = patch.name;
    if (patch.category !== undefined) body.metadata = { category: patch.category };
    if (patch.chatHistory !== undefined) body.chatHistory = patch.chatHistory;
    const res = await fetch(`${baseUrl()}/api/session/${encodeURIComponent(id)}`, {
      method: "PUT",
      headers: headers(),
      body: JSON.stringify(body),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function deleteSessionBackend(id: string): Promise<boolean> {
  if (!token()) return false;
  try {
    const res = await fetch(`${baseUrl()}/api/session/${encodeURIComponent(id)}`, {
      method: "DELETE",
      headers: headers(),
    });
    return res.ok;
  } catch {
    return false;
  }
}
