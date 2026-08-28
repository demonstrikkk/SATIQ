import { Router, Response } from 'express';
import { AuthenticatedRequest } from '../middleware/auth';

const router = Router();
const ORCHESTRATOR_URL = process.env.ORCHESTRATOR_URL || 'http://localhost:8000';

router.post('/', async (req: AuthenticatedRequest, res: Response) => {
  const userId = req.user?.userId;
  if (!userId) {
    return res.status(401).json({ error: 'User context not found' });
  }

  const { query, assets, sessionId } = req.body;

  if (!query) {
    return res.status(400).json({ error: 'Query is required' });
  }

  try {
    // Forward query and assets to Orchestrator Python service
    const response = await fetch(`${ORCHESTRATOR_URL}/api/orchestrator/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': userId,
        'X-Session-Id': sessionId || ''
      },
      body: JSON.stringify({
        query,
        assets,
        userId,
        sessionId
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      return res.status(response.status).json({
        error: 'Orchestrator error',
        details: errorText
      });
    }

    const data = await response.json();
    return res.status(200).json(data);
  } catch (error: any) {
    // Fallback/Mock behavior if orchestrator is not running or hasn't been implemented yet
    console.warn('Orchestrator service unavailable, falling back to mock response:', error.message);
    
    return res.status(200).json({
      message: 'Query received (Mocked Response: Orchestrator service is currently offline or not implemented)',
      query,
      userId,
      sessionId,
      status: 'STUB_FALLBACK',
      execution_trace: {
        task: 'mock_query_resolution',
        steps: ['gateway_receive', 'orchestrator_fallback_stub'],
        timestamp: new Date().toISOString()
      }
    });
  }
});

export default router;
