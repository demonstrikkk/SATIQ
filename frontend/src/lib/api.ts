const BASE = import.meta.env.VITE_API_BASE ?? "";

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Accept":"application/json" }});
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method:"POST", headers:{ "Content-Type":"application/json", "Accept":"application/json"}, body: JSON.stringify(body)});
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}
export async function apiUpload<T>(path: string, file: File, extra?: Record<string,string>): Promise<T> {
  const fd = new FormData();
  fd.append("file", file);
  if (extra) Object.entries(extra).forEach(([k,v])=> fd.append(k,v));
  const res = await fetch(`${BASE}${path}`, { method:"POST", body: fd });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// typed helpers matching gateway contracts
export interface QueryRequest { session_id: string; query: string; image_refs?: string[]; spatial_refs?: string[]; }
export interface AssetMeta { id: string; filename: string; crs: string; resolution: number; bands: string[]; acquired: string; platform: string; cloud_cover?: number; }
