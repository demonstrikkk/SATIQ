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
  const safeSessionId = sessionId.replace(/[^a-zA-Z0-9_-]/g, '');
  const safeUserId = userId.replace(/[^a-zA-Z0-9_-]/g, '');
  return path.join(sessionDir, `${safeUserId}_${safeSessionId}.json`);
};

// Single-user helper: find session file regardless of owner prefix.
// For "we are the only user" dev, old sessions with random usr_* prefix must remain accessible
// after re-login with deterministic usr_demo. Searches for "*_{sessionId}.json".
const findSessionFile = (sessionId: string): string | null => {
  const safeSessionId = sessionId.replace(/[^a-zA-Z0-9_-]/g, '');
  try {
    const files = fs.readdirSync(sessionDir);
    const match = files.find(f => f.endsWith(`_${safeSessionId}.json`));
    if (match) return path.join(sessionDir, match);
  } catch {}
  return null;
};

// GET /api/sessions - List all sessions for the current user
// Single-user dev: returns all sessions regardless of owner prefix so old
// sessions with random usr_* remain visible after deterministic usr_demo login.
router.get('/', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  try {
    const files = fs.readdirSync(sessionDir);
    const safeUserId = userId.replace(/[^a-zA-Z0-9_-]/g, '');
    let filtered = files.filter(file => file.startsWith(`${safeUserId}_`) && file.endsWith('.json'));
    // Fallback for single-user: if no user-specific sessions, return all json sessions
    // This heals orphaned sessions from previous random userId logins.
    if (filtered.length === 0) {
      filtered = files.filter(file => file.endsWith('.json'));
    }
    const userSessions = filtered
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

  let filePath = getSessionFilePath(userId, sessionId);
  // Single-user fallback: if not found under current user, search any owner
  if (!fs.existsSync(filePath)) {
    const found = findSessionFile(sessionId);
    if (found) filePath = found;
  }

  if (!fs.existsSync(filePath)) {
    // idempotent — frontend may ref stale ids after restart; don't spam 404
    return res.status(200).json({ sessionId, notFound: true });
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
  const { name, metadata, sessionId: reqSessionId } = req.body || {};

  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  // Accept a client-supplied sessionId (must be safe) so frontend + backend ids stay in sync.
  const safeId = typeof reqSessionId === 'string' && /^[a-zA-Z0-9_-]{1,64}$/.test(reqSessionId)
    ? reqSessionId
    : `sess_${Math.random().toString(36).substr(2, 9)}`;
  const filePath = getSessionFilePath(userId, safeId);

  const newSession = {
    sessionId: safeId,
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

  let filePath = getSessionFilePath(userId, sessionId);
  // Single-user fallback: migrate orphaned file if found under old user
  if (!fs.existsSync(filePath)) {
    const found = findSessionFile(sessionId);
    if (found) filePath = found;
  }

  if (!fs.existsSync(filePath)) {
    // upsert on PUT — avoids 404 noise when frontend syncs after gateway restart
    const fresh = {
      sessionId,
      userId,
      name: name || `Session ${new Date().toLocaleString()}`,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      metadata: metadata || {},
      chatHistory: chatHistory || [],
    };
    try {
      fs.writeFileSync(filePath, JSON.stringify(fresh, null, 2), 'utf-8');
      return res.status(200).json(fresh);
    } catch (error: any) {
      return res.status(500).json({ error: 'Failed to create session on update', details: error.message });
    }
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

  let filePath = getSessionFilePath(userId, sessionId);
  if (!fs.existsSync(filePath)) {
    const found = findSessionFile(sessionId);
    if (found) filePath = found;
  }

  if (!fs.existsSync(filePath)) {
    // idempotent delete — frontend may double-delete on fast nav
    return res.status(200).json({ message: 'Session already absent', sessionId });
  }

  try {
    fs.unlinkSync(filePath);
    return res.status(200).json({ message: 'Session deleted successfully', sessionId });
  } catch (error: any) {
    return res.status(500).json({ error: 'Failed to delete session', details: error.message });
  }
});

export default router;
