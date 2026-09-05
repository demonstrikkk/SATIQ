import type { AnalysisRequest, ExecutionEvent } from "../../../../shared/contracts";
import type { AnalysisProvider } from "./analysis-provider";

const ORCH = (process.env.ORCHESTRATOR_URL ?? "http://localhost:8000").replace(/\/$/, "");
// polling is fallback; SSE/WS preferred. Increased from 500ms → 1200ms to cut 60% of GET spam
// while still feeling live (frontend itself streams via SSE, this is just gateway→orchestrator).
const POLL_MS = Number(process.env.ORCH_POLL_MS ?? 1200);
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
      (body as any).asset_ids = request.asset_ids;
      (body as any).image_ids = request.asset_ids;
      // Enrich asset_ids → assets[] with real CRS/GSD/width/height from upload store
      // so orchestrator _normalize_assets passes with ALLOW_SYNTHETIC_ASSETS=false.
      try {
        const { assetStore } = await import('../../store/assetStore');
        const enriched = assetStore.getMany(request.asset_ids);
        if (enriched.length > 0) {
          (body as any).assets = enriched.map(a => ({
            asset_id: a.asset_id,
            crs: (a as any).crs,
            gsd: (a as any).gsd ?? 10.0,
            width: (a as any).width,
            height: (a as any).height,
            bands: (a as any).bands,
            filename: a.filename,
          }));
        }
      } catch {}
      // Fallback: orchestrator image_pipeline.resolve_asset will also try filesystem lookup
    }
    if (request.spatial_refs) (body as any).spatial_refs = request.spatial_refs;

    let sessionId: string;
    try {
      const authHeader = (request as any)._authHeader as string | undefined;
      const res = await fetch(`${ORCH}/api/v1/task`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
          ...(authHeader ? { Authorization: authHeader } : {}),
        },
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

    // 2. Prefer orchestrator SSE — use native async iterable (undici/Node fetch) with ReadableStream fallback
    try {
      const authHeader2 = (request as any)._authHeader as string | undefined;
      const sseRes = await fetch(`${ORCH}/api/v1/task/${encodeURIComponent(sessionId)}/stream`, {
        headers: {
          Accept: "text/event-stream",
          ...(authHeader2 ? { Authorization: authHeader2 } : {}),
        },
        signal,
      } as any);
      if (sseRes.ok && sseRes.body) {
        const decoder = new TextDecoder();
        let buf = "";
        let lastStatusSSE: string | undefined;
        // Unified async iteration: supports both Web ReadableStream (getReader) and Node Readable (async iterable)
        const body: any = sseRes.body;
        const isWebStream = typeof body.getReader === "function";
        if (isWebStream) {
          const reader = body.getReader();
          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            let idx;
            while ((idx = buf.indexOf("\n\n")) !== -1) {
              const frame = buf.slice(0, idx);
              buf = buf.slice(idx + 2);
              const dataLine = frame.split("\n").find((l: string) => l.startsWith("data: "));
              if (!dataLine) continue;
              try {
                const ev = JSON.parse(dataLine.slice(6)) as ExecutionEvent;
                yield ev as ExecutionEvent;
                if ((ev as any).event === "query_completed" || (ev as any).event === "final_answer") lastStatusSSE = "completed";
              } catch {}
            }
            if (signal.aborted) return;
          }
        } else {
          // Node Readable async iterable path (undici)
          for await (const chunk of body as AsyncIterable<Uint8Array>) {
            buf += decoder.decode(chunk as Uint8Array, { stream: true });
            let idx;
            while ((idx = buf.indexOf("\n\n")) !== -1) {
              const frame = buf.slice(0, idx);
              buf = buf.slice(idx + 2);
              const dataLine = frame.split("\n").find((l: string) => l.startsWith("data: "));
              if (!dataLine) continue;
              try {
                const ev = JSON.parse(dataLine.slice(6)) as ExecutionEvent;
                yield ev as ExecutionEvent;
                if ((ev as any).event === "query_completed" || (ev as any).event === "final_answer") lastStatusSSE = "completed";
              } catch {}
            }
            if (signal.aborted) return;
          }
        }
        if (lastStatusSSE === "completed") return;
      }
    } catch {
      // SSE not available — fall through to polling
    }

    const seen = new Set<string>();
    let lastStatus: string | undefined;
    let attempts = 0;
    const maxAttempts = Math.min(Number(process.env.ORCH_POLL_MAX_ATTEMPTS ?? 32), 64); // cap 64 *1.2s ≈ 77s, respects TOTAL_BUDGET 15s
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
        // dedupe by payload id/timestamp, not index (reorders safe)
        for (const ev of data.events) {
          const dedupKey = `${ev.event}:${ev.timestamp ?? ''}:${JSON.stringify(ev.payload).slice(0, 80)}`;
          if (seen.has(dedupKey)) continue;
          seen.add(dedupKey);
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
