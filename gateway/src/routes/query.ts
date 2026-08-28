import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';
import { executionManager } from '../analysis/execution-manager';
import type { AnalysisRequest, ExecutionEvent } from '../../../shared/contracts';

const router = Router();

// POST /api/query — start an analysis execution
router.post('/', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const { query, session_id, asset_ids, spatial_refs } = req.body ?? {};
  if (!query || typeof query !== 'string' || query.trim().length === 0) {
    return res.status(400).json({ error: 'Query is required' });
  }
  if (query.length > 4000) {
    return res.status(400).json({ error: 'Query exceeds maximum length (4000 chars)' });
  }

  const request: AnalysisRequest = {
    query: query.trim(),
    session_id: typeof session_id === 'string' ? session_id : undefined,
    asset_ids: Array.isArray(asset_ids) ? asset_ids.filter((a) => typeof a === 'string') : undefined,
    spatial_refs:
      Array.isArray(spatial_refs) ? spatial_refs.filter((s) => typeof s === 'string') : undefined,
  };

  const execution = executionManager.create(request, userId);
  return res.status(202).json(execution);
});

// GET /api/query/:executionId/stream — SSE stream of execution events
router.get('/:executionId/stream', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  const { executionId } = req.params;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const exec = executionManager.get(executionId);
  if (!exec) {
    return res.status(404).json({ error: 'Execution not found' });
  }
  if (exec.userId !== userId) {
    return res.status(403).json({ error: 'Access denied' });
  }

  res.writeHead(200, {
    'Content-Type': 'text/event-stream; charset=utf-8',
    'Cache-Control': 'no-cache, no-transform',
    Connection: 'keep-alive',
    'X-Accel-Buffering': 'no',
  });

  // Flush helper — writes an SSE frame
  const send = (ev: ExecutionEvent) => {
    res.write(`event: ${ev.event}\n`);
    res.write(`data: ${JSON.stringify(ev)}\n\n`);
  };

  // Replay buffered events first, then subscribe for live ones.
  for (const ev of exec.events) send(ev);
  if (exec.finishedAt !== undefined) {
    res.end();
    return;
  }

  const unsubscribe = executionManager.subscribe(executionId, send);
  const unsubscribeFinish = executionManager.onFinish(executionId, () => {
    res.end();
  });

  // Cleanup on client disconnect
  req.on('close', () => {
    unsubscribe();
    unsubscribeFinish();
  });
});

// POST /api/query/:executionId/cancel — abort a running execution
router.post('/:executionId/cancel', (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  const { executionId } = req.params;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const exec = executionManager.get(executionId);
  if (!exec) {
    return res.status(404).json({ error: 'Execution not found' });
  }
  if (exec.userId !== userId) {
    return res.status(403).json({ error: 'Access denied' });
  }
  if (exec.finishedAt !== undefined) {
    return res.status(409).json({ error: 'Execution already finished', status: exec.status });
  }

  executionManager.cancel(executionId);
  return res.status(200).json({ message: 'Cancellation requested', execution_id: executionId });
});

export default router;