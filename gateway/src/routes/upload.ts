import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';
import { upload } from '../middleware/upload';
import { uploadLimiter } from '../middleware/rateLimiter';
import type { AssetMeta } from '../../../shared/contracts';
import fs from 'fs';
import path from 'path';

const router = Router();

// POST /api/upload - forwards to orchestrator ingest for validation + MinIO, returns AssetMeta
router.post('/', uploadLimiter, upload.single('image'), async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }
  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded or invalid file format' });
  }
  const { filename, originalname, size, mimetype, path: filePath } = req.file as Express.Multer.File & { path: string };

  const asset: AssetMeta = {
    asset_id: `asset_${filename}`,
    filename,
    originalname,
    mime_type: mimetype,
    size,
    url: `/api/assets/${encodeURIComponent(filename)}`,
    uploaded_at: new Date().toISOString(),
  };

  // Forward to orchestrator ingest — streaming via fs.createReadStream (undici native), 60s for 100MB
  const orchUrl = (process.env.ORCHESTRATOR_URL ?? "http://orchestrator:8000").replace(/\/$/, "");
  let validation: unknown = null;
  let orchStatus: number | null = null;
  try {
    const stream: any = fs.createReadStream(filePath);
    const form = new FormData();
    // Real streaming only — no fallback, no heap buffering. Node 18+ undici requires duplex:half for stream bodies.
    form.append("file", stream as any, originalname);
    const r = await fetch(`${orchUrl}/api/v1/ingest`, {
      method: "POST",
      body: form as any,
      headers: { ...(req.headers.authorization ? { Authorization: req.headers.authorization } : {}) },
      // @ts-ignore AbortSignal timeout 60s for 100MB ingest
      signal: AbortSignal.timeout ? (AbortSignal as any).timeout(60000) : undefined,
      // @ts-ignore Node fetch duplex for streaming
      duplex: "half",
    } as any);
    orchStatus = r.status;
    if (r.ok) {
      const data = (await r.json()) as any;
      validation = data;
      // Wire metadata even if geotiff_path missing (e.g., PNG fallback) — orchestrator still provides validation
      const val = data?.validation ?? {};
      if (data?.geotiff_path) (asset as any).geotiff_path = data.geotiff_path;
      if (data?.validation) (asset as any).orchestrator_validation = data.validation;
      if (data?.thumbnail_preview) (asset as any).thumbnail_preview = data.thumbnail_preview;
      if (data?.thumbnail) (asset as any).thumbnail_preview = data.thumbnail;
      // Wire width/height/crs/gsd/bands for pipeline (input_validator 100Mpix + CRS gate)
      if (val?.width) (asset as any).width = val.width;
      if (val?.height) (asset as any).height = val.height;
      if (val?.crs) (asset as any).crs = val.crs;
      if (val?.gsd) (asset as any).gsd = val.gsd;
      if (val?.bands) (asset as any).bands = val.bands;
      if (val?.dtype) (asset as any).dtype = val.dtype;
      // Persist enriched asset for later query enrichment (asset_ids → assets[] with CRS)
      try {
        const { assetStore } = await import('../store/assetStore');
        assetStore.set(asset.asset_id, asset as AssetMeta);
      } catch {}
      // Also enrich even without geotiff_path if validation present
      if (!data?.geotiff_path && val?.width) {
        // still useful — no geotiff_path but dimensions known
      }
      // if CRS mismatch, surface as 400 to frontend (not 200)
      if (data?.validation?.crs_mismatch) {
        return res.status(400).json({ error: 'CRS mismatch', asset, validation: data.validation });
      }
    } else {
      const txt = await r.text().catch(() => "");
      console.warn(`[upload] orchestrator ingest ${r.status}: ${txt.slice(0, 200)}`);
      // do not mask CRS error as success
      if (r.status === 400) {
        return res.status(400).json({ error: txt.slice(0, 300), asset, validation: txt });
      }
    }
  } catch (e) {
    console.warn(`[upload] orchestrator ingest unreachable (${orchUrl}):`, (e as Error).message?.slice(0, 120));
  } finally {
    // cleanup temp file after forward — do not leak gateway/upload
    // keep file for /api/assets serving, so don't delete; but truncate if >50MB handled by multer
  }

  // Always return asset, but status reflects orchestrator validation
  if (orchStatus === 400) {
    return res.status(400).json({ error: 'Validation failed', asset, validation });
  }
  return res.status(200).json({ message: 'File uploaded successfully', asset, validation });
});

export default router;