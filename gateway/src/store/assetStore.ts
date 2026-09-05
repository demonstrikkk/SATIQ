import type { AssetMeta } from '../../../shared/contracts';

// In-memory asset registry — survives for gateway lifetime, used to enrich
// query asset_ids → assets[] with real CRS/GSD/width/height so orchestrator
// _normalize_assets doesn't reject with ALLOW_SYNTHETIC_ASSETS=false.
// Entries expire after 1h (same as orchestrator EXECUTIONS TTL).
const store = new Map<string, { asset: AssetMeta; expires: number }>();
const TTL_MS = 60 * 60 * 1000;

export const assetStore = {
  set(id: string, asset: AssetMeta) {
    store.set(id, { asset, expires: Date.now() + TTL_MS });
    // also index by filename without asset_ prefix for resolve flexibility
    if (id.startsWith('asset_')) {
      const short = id.slice(6);
      store.set(short, { asset, expires: Date.now() + TTL_MS });
    }
  },
  get(id: string): AssetMeta | undefined {
    const e = store.get(id);
    if (!e) return undefined;
    if (Date.now() > e.expires) { store.delete(id); return undefined; }
    return e.asset;
  },
  getMany(ids: string[]): AssetMeta[] {
    return ids.map(id => this.get(id)).filter(Boolean) as AssetMeta[];
  },
  delete(id: string) { store.delete(id); },
  clear() { store.clear(); },
};
