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

  // Forward to orchestrator ingest for GeoTIFF validation + thumbnail + MinIO (best-effort)
  const orchUrl = (process.env.ORCHESTRATOR_URL ?? "http://orchestrator:8000").replace(/\/$/, "");
  let validation: unknown = null;
  try {
    const buf = fs.readFileSync(filePath);
    const form = new FormData();
    form.append("file", new Blob([buf], { type: mimetype }) as any, originalname);
    form.append("crs", "EPSG:4326");
    const r = await fetch(`${orchUrl}/api/v1/ingest`, { method: "POST", body: form as any });
    if (r.ok) {
      const data = (await r.json()) as any;
      validation = data;
      // enrich asset_id from orchestrator if provided (geotiff_path)
      if (data?.geotiff_path) {
        const base = path.basename(data.geotiff_path);
        (asset as any).geotiff_path = data.geotiff_path;
        (asset as any).orchestrator_validation = data.validation;
        (asset as any).thumbnail_preview = data.thumbnail_preview;
      }
    } else {
      const txt = await r.text().catch(() => "");
      console.warn(`[upload] orchestrator ingest ${r.status}: ${txt.slice(0, 200)}`);
    }
  } catch (e) {
    console.warn(`[upload] orchestrator ingest unreachable (${orchUrl}):`, (e as Error).message?.slice(0, 120));
  }

  return res.status(200).json({ message: 'File uploaded successfully', asset, validation });
});

export default router;