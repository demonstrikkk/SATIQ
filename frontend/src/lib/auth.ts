/**
 * Auth helpers — token storage + login against the gateway's stub auth.
 * The gateway accepts any non-empty credentials and returns a 24h JWT.
 */
const TOKEN_KEY = "satiq_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(t: string) {
  try {
    localStorage.setItem(TOKEN_KEY, t);
  } catch {}
}

export function clearToken() {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {}
}

function baseUrl(): string {
  return (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "") || "";
}

export async function login(username: string, password: string): Promise<string> {
  const res = await fetch(`${baseUrl()}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error(`Login failed (${res.status})`);
  const data = (await res.json()) as { token?: string; user?: { username: string } };
  if (!data.token) throw new Error("No token returned");
  setToken(data.token);
  return data.token;
}

export async function loginAsDemo(): Promise<string> {
  return login("demo", "demo");
}

/**
 * Ensure a JWT exists for API calls. If absent, auto-log in (demo stub) to
 * obtain one. This is the single source of the auth token used across the app,
 * and replaces a visible login screen — we are the only user, so a token is
 * minted transparently and attached to every request.
 */
export async function ensureToken(): Promise<string | null> {
  const existing = getToken();
  if (existing) return existing;
  try {
    const res = await fetch(`${baseUrl()}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "demo", password: "demo" }),
    });
    if (!res.ok) return null;
    const data = (await res.json()) as { token?: string };
    if (data.token) {
      setToken(data.token);
      return data.token;
    }
  } catch {}
  return null;
}
