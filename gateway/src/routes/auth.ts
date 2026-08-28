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

  // STUB: demo-stage auth — any non-empty credentials are accepted and mapped to
  // a fresh user id. Replace with a real identity provider before external deployment.
  const userId = `usr_${Math.random().toString(36).slice(2, 11)}`;
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
