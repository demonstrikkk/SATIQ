import { Router, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

const router = Router();

router.post('/login', (req: Request, res: Response) => {
  const { username, password } = req.body;

  if (!username || typeof username !== 'string' || username.trim().length === 0) {
    return res.status(400).json({ error: 'Username is required' });
  }
  if (!password || typeof password !== 'string' || password.length === 0) {
    return res.status(400).json({ error: 'Password is required' });
  }

  const secret = process.env.JWT_SECRET;
  if (!secret) {
    console.error('[auth] JWT_SECRET is not configured — refusing to issue tokens.');
    return res.status(500).json({ error: 'Server authentication is not configured (JWT_SECRET missing)' });
  }

  // Single-user dev: deterministic userId per username so sessions survive
  // re-login / token refresh. Random IDs caused "session belongs to another user"
  // 403s when gateway restarted or token refreshed.
  const cleanName = username.trim().toLowerCase();
  const userId = `usr_${cleanName.replace(/[^a-z0-9]/g, "") || "demo"}`;
  const token = jwt.sign(
    { userId, username: username.trim() },
    secret,
    { expiresIn: '24h' }
  );

  return res.status(200).json({
    message: 'Login successful',
    token,
    user: {
      userId,
      username: username.trim()
    }
  });
});

export default router;
