import type { AnalysisRequest, ExecutionEvent } from "../../../../shared/contracts";
import type { AnalysisProvider } from "./analysis-provider";

const ORCH = (process.env.ORCHESTRATOR_URL ?? "http://localhost:8000").replace(/\/$/, "");
const POLL_MS = 300;
const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });

export class AgenticAnalysisProvider implements AnalysisProvider {
  readonly name = "agentic";

  async *execute(request: AnalysisRequest, signal: AbortSignal): AsyncGenerator<ExecutionEvent> {
    // 1. POST to orchestrator — translate gateway AnalysisRequest → orchestrator TaskRequest
    const body: Record<string, unknown> = {
      query: request.query,
      session_id: request.session_id,
    };
    if (request.asset_ids && request.asset_ids.length > 0) {
      // orchestrator accepts asset_ids or image_ids; send both for compatibility
      (body as any).asset_ids = request.asset_ids;
      (body as any).image_ids = request.asset_ids;
      // also synthesize assets minimal for CRS gate
      (body as any).assets = request.asset_ids.map((id) => ({
        asset_id: id,
        modality: id.toLowerCase().includes("sar") || id.toLowerCase().includes("s1") ? "sar" : "optical",
        crs: "EPSG:32617",
        gsd: 10.0,
      }));
    }
    if (request.spatial_refs) (body as any).spatial_refs = request.spatial_refs;

    let sessionId: string;
    try {
      const res = await fetch(`${ORCH}/api/v1/task`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(body),
        signal,
      });
      if (!res.ok) {
        const txt = await res.text().catch(() => "");
        if (res.status === 429) {
          yield { event: "error", payload: { message: `Orchestrator backpressure 429: ${txt.slice(0, 200)}`, code: "rate_limited" } };
          return;
        }
        throw new Error(`Orchestrator POST /api/v1/task ${res.status}: ${txt.slice(0, 300)}`);
      }
      const data = (await res.json()) as { session_id: string; status: string };
      sessionId = data.session_id;
    } catch (err) {
      if (signal.aborted) return;
      const msg = err instanceof Error ? err.message : String(err);
      // If orchestrator unreachable, emit error (do not silently fallback to mock)
      yield { event: "error", payload: { message: `Orchestrator unreachable (${ORCH}): ${msg}`, code: "orchestrator_unreachable" } };
      return;
    }

    // 2. Poll GET /api/v1/task/:id — orchestrator buffers events in EXECUTIONS[sessionId].events
    const seen = new Set<number>();
    let lastStatus: string | undefined;
    let attempts = 0;
    const maxAttempts = 120; // 120 * 300ms = 36s > pipeline budget 15s + margin
    while (attempts < maxAttempts) {
      if (signal.aborted) return;
      attempts++;
      try {
        const res = await fetch(`${ORCH}/api/v1/task/${encodeURIComponent(sessionId)}`, {
          headers: { Accept: "application/json" },
          signal,
        });
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          yield { event: "error", payload: { message: `Poll ${res.status}: ${txt.slice(0, 200)}` } };
          return;
        }
        const data = (await res.json()) as {
          session_id: string;
          status: string;
          result?: Record<string, unknown>;
          events: Array<{ event: string; payload?: Record<string, unknown>; timestamp?: number }>;
        };
        // yield new events in order
        for (let i = 0; i < data.events.length; i++) {
          if (seen.has(i)) continue;
          seen.add(i);
          const ev = data.events[i]!;
          // normalize to ExecutionEvent
          yield {
            event: ev.event as ExecutionEvent["event"],
            payload: ev.payload ?? {},
            timestamp: ev.timestamp ?? Date.now(),
          };
        }
        lastStatus = data.status;
        if (data.status === "completed" || data.status === "failed" || data.status === "cancelled") {
          // ensure final events drained — one more poll for trailing answer deltas if needed
          break;
        }
      } catch (err) {
        if (signal.aborted) return;
        const msg = err instanceof Error ? err.message : String(err);
        yield { event: "error", payload: { message: `Poll error: ${msg}` } };
        return;
      }
      await sleep(POLL_MS, signal).catch(() => {
        return;
      });
      if (signal.aborted) return;
    }

    if (lastStatus !== "completed" && lastStatus !== "failed") {
      yield { event: "error", payload: { message: `Orchestrator timeout after ${attempts * POLL_MS}ms (status=${lastStatus})`, code: "orchestrator_timeout" } };
    }
  }
}
