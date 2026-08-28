import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';
import { upload } from '../middleware/upload';
import { uploadLimiter } from '../middleware/rateLimiter';
import type { AssetMeta } from '../../../shared/contracts';

const router = Router();

// POST /api/upload - Handle file upload, returns the shared AssetMeta contract
router.post('/', uploadLimiter, upload.single('image'), (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded or invalid file format' });
  }

  const { filename, originalname, size, mimetype } = req.file;

  const asset: AssetMeta = {
    asset_id: `asset_${filename}`,
    filename,
    originalname,
    mime_type: mimetype,
    size,
    url: `/api/assets/${encodeURIComponent(filename)}`,
    uploaded_at: new Date().toISOString(),
  };

  return res.status(200).json({ message: 'File uploaded successfully', asset });
});

export default router;