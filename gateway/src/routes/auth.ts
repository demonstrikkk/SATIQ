import { Router, Request, Response } from 'express';
import jwt from 'jsonwebtoken';

const router = Router();

router.post('/login', (req: Request, res: Response) => {
  const { username, password } = req.body;

  if (!username) {
    return res.status(400).json({ error: 'Username is required' });
  }

  // Simple authentication: accept any non-empty username/password for demo/development purposes
  const userId = `usr_${Math.random().toString(36).substr(2, 9)}`;
  const secret = process.env.JWT_SECRET || 'supersecretkeyreplaceinproduction';
  
  const token = jwt.sign(
    { userId, username },
    secret,
    { expiresIn: '24h' }
  );

  return res.status(200).json({
    message: 'Login successful',
    token,
    user: {
      userId,
      username
    }
  });
});

export default router;
