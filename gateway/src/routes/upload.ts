import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';
import { upload } from '../middleware/upload';
import { uploadLimiter } from '../middleware/rateLimiter';
import path from 'path';

const router = Router();

// POST /api/upload - Handle file upload
router.post('/', uploadLimiter, upload.single('image'), (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  if (!req.file) {
    return res.status(400).json({ error: 'No file uploaded or invalid file format' });
  }

  const { filename, originalname, path: filePath, size, mimetype } = req.file;

  return res.status(200).json({
    message: 'File uploaded successfully',
    asset: {
      filename,
      originalname,
      path: filePath,
      size,
      mimetype,
      uploadedAt: new Date().toISOString()
    }
  });
});

export default router;
