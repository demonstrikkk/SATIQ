import { randomUUID } from 'crypto';
import type {
  AnalysisExecution,
  AnalysisRequest,
  ExecutionEvent,
} from '../../../shared/contracts';
import { selectProvider, type AnalysisProvider } from './providers/analysis-provider';

interface RunningExecution {
  executionId: string;
  userId: string;
  request: AnalysisRequest;
  status: AnalysisExecution['status'];
  events: ExecutionEvent[];
  listeners: Set<(ev: ExecutionEvent) => void>;
  finishListeners: Set<() => void>;
  abortController: AbortController;
  createdAt: number;
  finishedAt?: number;
}

/**
 * ExecutionManager — owns the lifecycle of every query execution:
 * create → run provider → buffer events → fan out to SSE subscribers → terminal state.
 * Executions are kept in memory (single-process gateway); a future orchestrator
 * service can replace the provider without touching this boundary.
 */
export class ExecutionManager {
  private executions = new Map<string, RunningExecution>();
  private provider: AnalysisProvider;

  constructor(provider?: AnalysisProvider) {
    this.provider = provider ?? selectProvider();
  }

  /** Create an execution and start running the provider in the background. */
  create(request: AnalysisRequest, userId: string): AnalysisExecution {
    const executionId = `exec_${randomUUID().slice(0, 8)}`;
    const now = Date.now();
    const exec: RunningExecution = {
      executionId,
      userId,
      request,
      status: 'queued',
      events: [],
      listeners: new Set(),
      finishListeners: new Set(),
      abortController: new AbortController(),
      createdAt: now,
    };
    this.executions.set(executionId, exec);
    void this.run(exec);
    return {
      execution_id: executionId,
      session_id: request.session_id,
      status: exec.status,
      created_at: new Date(now).toISOString(),
    };
  }

  get(executionId: string): RunningExecution | undefined {
    return this.executions.get(executionId);
  }

  /** Subscribe to live events for an execution. Returns an unsubscribe fn. */
  subscribe(executionId: string, onEvent: (ev: ExecutionEvent) => void): () => void {
    const exec = this.executions.get(executionId);
    if (!exec) return () => {};
    exec.listeners.add(onEvent);
    return () => {
      exec.listeners.delete(onEvent);
    };
  }

  /** Subscribe to terminal-state notifications. Returns an unsubscribe fn. */
  onFinish(executionId: string, cb: () => void): () => void {
    const exec = this.executions.get(executionId);
    if (!exec) return () => {};
    if (exec.finishedAt !== undefined) {
      cb();
      return () => {};
    }
    exec.finishListeners.add(cb);
    return () => {
      exec.finishListeners.delete(cb);
    };
  }

  cancel(executionId: string): boolean {
    const exec = this.executions.get(executionId);
    if (!exec || exec.finishedAt !== undefined) return false;
    exec.abortController.abort();
    return true;
  }

  private async run(exec: RunningExecution): Promise<void> {
    exec.status = 'running';
    try {
      for await (const ev of this.provider.execute(exec.request, exec.abortController.signal)) {
        if (exec.abortController.signal.aborted) break;
        exec.events.push(ev);
        for (const l of exec.listeners) l(ev);
      }

      if (exec.abortController.signal.aborted) {
        exec.status = 'cancelled';
        this.push(exec, { event: 'cancelled', payload: { reason: 'cancelled_by_user' } });
      } else {
        exec.status = 'completed';
      }
    } catch (err) {
      exec.status = 'failed';
      const message = err instanceof Error ? err.message : String(err);
      console.error(`[execution ${exec.executionId}] failed:`, message);
      this.push(exec, { event: 'error', payload: { message } });
    } finally {
      exec.finishedAt = Date.now();
      for (const cb of exec.finishListeners) cb();
      exec.finishListeners.clear();
      exec.listeners.clear();
    }
  }

  private push(exec: RunningExecution, ev: ExecutionEvent): void {
    const stamped: ExecutionEvent = { ...ev, timestamp: Date.now() };
    exec.events.push(stamped);
    for (const l of exec.listeners) l(stamped);
  }
}

export const executionManager = new ExecutionManager();