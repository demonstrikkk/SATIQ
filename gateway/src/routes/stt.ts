import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';
import multer from 'multer';

const router = Router();

const ORCH = (process.env.ORCHESTRATOR_URL ?? 'http://localhost:8000').replace(/\/$/, '');

const ALLOWED_AUDIO = ['.wav', '.mp3', '.m4a', '.ogg', '.flac', '.webm', '.oga'];

const audioUpload = multer({
  storage: multer.memoryStorage(),
  limits: { fileSize: 25 * 1024 * 1024 }, // Groq 25MB cap
  fileFilter: (_req, file, cb) => {
    const ext = (file.originalname.split('.').pop() ?? '').toLowerCase();
    if (ALLOWED_AUDIO.includes(`.${ext}`)) cb(null, true);
    else cb(new Error(`Unsupported audio type: .${ext}`));
  },
});

// Speech-to-text: forwards audio to the orchestrator's Groq Whisper endpoint.
// Returns { text } (mock fallback when no GROQ_API_KEY configured upstream).
router.post(
  '/',
  (req: AuthenticatedRequest, res: Response, next) => {
    // auth + body parsing already handled by global middleware; ensure user context
    if (!req.user?.userId) return res.status(401).json({ error: 'User context not found' });
    next();
  },
  audioUpload.single('file'),
  async (req: AuthenticatedRequest, res: Response) => {
    if (!req.file) return res.status(400).json({ error: 'Audio file required (field "file")' });
    try {
      const form = new FormData();
      form.append(
        'file',
        new Blob([req.file.buffer as unknown as BlobPart], { type: req.file.mimetype || 'application/octet-stream' }),
        req.file.originalname,
      );
      if (req.body.language) form.append('language', req.body.language);
      if (req.body.prompt) form.append('prompt', req.body.prompt);

      const orchRes = await fetch(`${ORCH}/api/v1/transcribe`, {
        method: 'POST',
        body: form,
        headers: { Authorization: req.headers['authorization'] || '' },
      });
      const data = (await orchRes.json().catch(() => ({}))) as Record<string, any>;
      if (!orchRes.ok) {
        return res.status(orchRes.status === 502 ? 502 : 500).json({
          error: (data && data.error) || 'Transcription failed',
        });
      }
      return res.status(200).json({ text: data.text || '', transcription: data });
    } catch (e: any) {
      return res.status(500).json({ error: `STT gateway error: ${e?.message || e}` });
    }
  },
);

export default router;
