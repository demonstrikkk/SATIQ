const BASE = import.meta.env.VITE_API_BASE ?? "";

function authHeaders(): Record<string,string> {
  const tok = localStorage.getItem("satiq_token");
  return tok ? { Authorization: `Bearer ${tok}` } : {};
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { headers: { "Accept":"application/json", ...authHeaders() }});
  if (!res.ok) {
    const body = await res.text().catch(()=> "");
    throw new Error(`${res.status} ${res.statusText} ${body.slice(0,200)}`);
  }
  return res.json() as Promise<T>;
}
export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method:"POST", headers:{ "Content-Type":"application/json", "Accept":"application/json", ...authHeaders()}, body: JSON.stringify(body)});
  if (!res.ok) {
    const body = await res.text().catch(()=> "");
    throw new Error(`${res.status} ${res.statusText} ${body.slice(0,300)}`);
  }
  return res.json() as Promise<T>;
}
export async function apiUpload<T>(path: string, file: File, extra?: Record<string,string>): Promise<T> {
  const fd = new FormData();
  fd.append("image", file);
  if (extra) Object.entries(extra).forEach(([k,v])=> fd.append(k,v));
  const res = await fetch(`${BASE}${path}`, { method:"POST", headers: { ...authHeaders() }, body: fd });
  if (!res.ok) {
    const body = await res.text().catch(()=> "");
    throw new Error(`${res.status} ${res.statusText} ${body.slice(0,300)}`);
  }
  return res.json() as Promise<T>;
}

// typed helpers matching gateway contracts
export interface QueryRequest { session_id: string; query: string; image_refs?: string[]; spatial_refs?: string[]; }
export interface AssetMeta { id: string; filename: string; crs: string; resolution: number; bands: string[]; acquired: string; platform: string; cloud_cover?: number; }
