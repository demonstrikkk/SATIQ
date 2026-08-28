import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';
import path from 'path';
import fs from 'fs';

const router = Router();
const sessionDir = path.join(__dirname, '../../session');

// Ensure session directory exists
if (!fs.existsSync(sessionDir)) {
  fs.mkdirSync(sessionDir, { recursive: true });
}

// Helper to sanitize session ID and get safe file path
const getSessionFilePath = (userId: string, sessionId: string): string => {
  // Regex validation: only alphanumeric, hyphens, and underscores allowed
  const safeSessionId = sessionId.replace(/[^a-zA-Z0-9_-]/g, '');
  const safeUserId = userId.replace(/[^a-zA-Z0-9_-]/g, '');
  return path.join(sessionDir, `${safeUserId}_${safeSessionId}.json`);
};

// GET /api/sessions - List all sessions for the current user
router.get('/', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  try {
    const files = fs.readdirSync(sessionDir);
    const safeUserId = userId.replace(/[^a-zA-Z0-9_-]/g, '');
    const userSessions = files
      .filter(file => file.startsWith(`${safeUserId}_`) && file.endsWith('.json'))
      .map(file => {
        const filePath = path.join(sessionDir, file);
        const data = fs.readFileSync(filePath, 'utf-8');
        try {
          return JSON.parse(data);
        } catch {
          return null;
        }
      })
      .filter(Boolean);

    return res.status(200).json(userSessions);
  } catch (error: any) {
    return res.status(500).json({ error: 'Failed to retrieve sessions', details: error.message });
  }
});

// GET /api/sessions/:id - Get specific session
router.get('/:id', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  const sessionId = req.params.id;

  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const filePath = getSessionFilePath(userId, sessionId);

  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Session not found or access denied' });
  }

  try {
    const data = fs.readFileSync(filePath, 'utf-8');
    const session = JSON.parse(data);
    return res.status(200).json(session);
  } catch (error: any) {
    return res.status(500).json({ error: 'Failed to read session data', details: error.message });
  }
});

// POST /api/sessions - Create a new session
router.post('/', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  const { name, metadata } = req.body;

  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const sessionId = `sess_${Math.random().toString(36).substr(2, 9)}`;
  const filePath = getSessionFilePath(userId, sessionId);

  const newSession = {
    sessionId,
    userId,
    name: name || `Session ${new Date().toLocaleString()}`,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    metadata: metadata || {},
    chatHistory: []
  };

  try {
    fs.writeFileSync(filePath, JSON.stringify(newSession, null, 2), 'utf-8');
    return res.status(201).json(newSession);
  } catch (error: any) {
    return res.status(500).json({ error: 'Failed to create session', details: error.message });
  }
});

// PUT /api/sessions/:id - Update existing session
router.put('/:id', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  const sessionId = req.params.id;
  const { name, metadata, chatHistory } = req.body;

  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const filePath = getSessionFilePath(userId, sessionId);

  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Session not found or access denied' });
  }

  try {
    const data = fs.readFileSync(filePath, 'utf-8');
    const existingSession = JSON.parse(data);

    const updatedSession = {
      ...existingSession,
      name: name !== undefined ? name : existingSession.name,
      metadata: metadata !== undefined ? { ...existingSession.metadata, ...metadata } : existingSession.metadata,
      chatHistory: chatHistory !== undefined ? chatHistory : existingSession.chatHistory,
      updatedAt: new Date().toISOString()
    };

    fs.writeFileSync(filePath, JSON.stringify(updatedSession, null, 2), 'utf-8');
    return res.status(200).json(updatedSession);
  } catch (error: any) {
    return res.status(500).json({ error: 'Failed to update session', details: error.message });
  }
});

// DELETE /api/sessions/:id - Delete a session
router.delete('/:id', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  const sessionId = req.params.id;

  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const filePath = getSessionFilePath(userId, sessionId);

  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'Session not found or access denied' });
  }

  try {
    fs.unlinkSync(filePath);
    return res.status(200).json({ message: 'Session deleted successfully', sessionId });
  } catch (error: any) {
    return res.status(500).json({ error: 'Failed to delete session', details: error.message });
  }
});

export default router;
