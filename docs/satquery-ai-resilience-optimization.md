# SatQuery AI — Pipeline Resilience & Performance Optimization Spec

**Target:** LangGraph RS-VLM pipeline (SIH 2026 PS 26167)
**Goal:** Zero downtime, low latency, fault tolerance, high availability
**Audience:** Coding agent implementing changes against the existing LangGraph graph

---

## 0. Context (read first)

This pipeline is an agentic vision-language system for remote-sensing image analysis:

```
start → User Input → Input Validator ★
   → [Router Agent | Planner Agent ★ | Encoder Selector ★]
   → Data & Preprocessing Agent ←→ Tile Manager ★
   → Co-reg Quality Gate ★ / Encoder Compat Check ★
   → Vision Encoder Agent (SatMAE / SSL4EO-S12 / Prithvi)
   → Multimodal Fusion Agent (Qwen 3.5 9B + adapter)
   → Task-Specific Agent (VQA / Caption / Ground / ChangeVQA / Fusion)
       ↔ Error Handler (retry/re-plan)
   → Post-Processing Agent (validate, geometa, stitch, confidence gate ★)
   → Response to User → end
```

Inputs: GeoTIFF image(s) (Sentinel-1 SAR, Sentinel-2 multispectral, or Cartosat-2S/RISAT for hidden eval) + natural-language query + task type.

The current graph has **no retry cap**, **no circuit breaker**, **no timeout budget propagation**, and **no separation between the orchestration layer and the GPU-bound model-serving layer**. These are the four things this spec fixes. Do not redesign the agent logic/business rules — only add the resilience/performance layer around the existing nodes.

---

## 1. Objectives (in priority order)

1. **Fault tolerance** — no single bad input or transient failure can hang or crash the whole pipeline.
2. **Low latency** — hard per-node timeout budgets; cache and batch where possible.
3. **Zero downtime** — model-serving tier and orchestration tier are independently deployable/scalable.
4. **Availability** — pipeline degrades gracefully under load or partial backend failure instead of failing outright.

---

## 2. Architectural changes

### 2.1 Split orchestration from model serving

- Keep the **LangGraph controller** (Router, Planner, Input Validator, Tile Manager, quality gates, Post-Processing) as a **thin, stateless** service.
- Move the two GPU-bound nodes into independently-scaled services behind their own API:
  - `vision-encoder-service` — serves SatMAE / SSL4EO-S12 / Prithvi, ≥2 replicas per encoder type.
  - `fusion-llm-service` — serves Qwen 3.5 9B + adapter (or wraps an external LLM API).
- The LangGraph controller calls these over HTTP/gRPC with a hard timeout (see §2.3). This lets you roll out changes to either tier without touching the other, and scale the expensive GPU tier independently of the cheap orchestration tier.

### 2.2 Request queue at the entry point

- `User Input` should enqueue the request (in-memory queue is fine for dummy-data testing; note where a real queue — e.g. Redis Streams/SQS — would go in production) rather than processing synchronously.
- Workers pull from the queue with backpressure (reject/429 when queue depth exceeds a configurable limit) instead of accepting unbounded concurrent requests.

### 2.3 Timeout budgets (propagate a deadline through graph state)

Add a `deadline_ms` field to the LangGraph state, set once at `Input Validator`, and check it before each expensive node. Suggested defaults (tune later against real hardware):

| Node | Timeout budget |
|---|---|
| Input Validator | 200ms |
| Data & Preprocessing Agent | 2000ms |
| Co-reg Quality Gate | 300ms |
| Vision Encoder Agent | 4000ms |
| Multimodal Fusion Agent | 6000ms |
| Task-Specific Agent | 2000ms |
| Post-Processing Agent | 500ms |
| **Total pipeline budget** | **~15s** |

If a node exceeds its budget, it must raise a typed `NodeTimeoutError` and route to the Error Handler — never hang silently.

### 2.4 Retry policy (bounded, and transient-vs-permanent aware)

The existing `retry ★` dashed loop (Task-Specific Agent → Error Handler → Post-Processing) currently has no cap. Replace with:

- **Max 2 retries** per request, exponential backoff (e.g. 200ms, 800ms).
- The Error Handler must classify the failure before deciding to retry:
  - **Transient** (LLM 429/rate-limit, timeout, connection reset, GPU OOM under load) → retry.
  - **Permanent** (malformed GeoTIFF, unsupported sensor type, schema validation failure, unsupported band count) → **do not retry**; short-circuit directly to a structured error response.
- After 2 failed retries on a transient error, also short-circuit to a structured error response (do not loop forever).
- Every retry must reuse cached/checkpointed state from before the expensive step (see §2.6) — never redo GeoTIFF decode/co-registration from scratch on retry.

### 2.5 Circuit breaker on the Fusion LLM call

- Wrap calls to `fusion-llm-service` in a circuit breaker (e.g. closed → open after N consecutive failures in a rolling window → half-open probe after cooldown).
- When open: either (a) fall back to a smaller/cheaper model, or (b) return a clearly-flagged degraded-mode response, rather than queuing/blocking every incoming request behind a known-broken backend.

### 2.6 Idempotency & checkpointing

- Compute a request key = `hash(image_bytes) + hash(query) + task_type`.
- After each expensive stage (preprocessing/co-reg, vision encoding), checkpoint intermediate state keyed by this hash (in-memory dict for dummy-data testing; note where Redis/a KV store would go in production).
- A retried request with the same key resumes from the last successful checkpoint instead of restarting the pipeline.

### 2.7 Validation gate failure paths

- `Co-reg Quality Gate` and `Encoder Compat Check` must have an explicit **reject** exit (not just an implicit dead-end): on failure, emit a structured rejection reason (e.g. `"coreg_ssim_below_threshold"`, `"encoder_modality_mismatch"`) and route to the Error Handler as a **permanent** failure (no retry).

### 2.8 Health checks & readiness

- Each backend service (`vision-encoder-service`, `fusion-llm-service`) exposes a `/health` endpoint.
- The Router Agent (or a lightweight readiness check before dispatch) skips/reroutes around unhealthy backends rather than dispatching blindly and waiting for a timeout every time.

### 2.9 Caching

- `Tile Manager`: cache tile grid/stitch metadata for repeated multi-temporal requests over the same AOI (TTL-based, in-memory for dummy testing).
- `Encoder Selector`: cache the modality→encoder mapping table in memory with a short TTL instead of a live lookup per request.

---

## 3. Implementation checklist

- [ ] Add `deadline_ms` and per-node timeout enforcement to graph state
- [ ] Refactor Vision Encoder Agent and Multimodal Fusion Agent to call out to separate service interfaces (even if, for now, those services are local stubs — the interface boundary is what matters)
- [ ] Implement bounded retry (max 2, exponential backoff) with transient/permanent classification in the Error Handler
- [ ] Implement circuit breaker wrapper around the fusion LLM call
- [ ] Implement request-key based checkpointing after preprocessing and after vision encoding
- [ ] Add explicit reject branches to Co-reg Quality Gate and Encoder Compat Check
- [ ] Add `/health` stub endpoints to both model-serving interfaces
- [ ] Add TTL caches for Tile Manager metadata and Encoder Selector mapping
- [ ] Add an entry-point queue with configurable max depth and backpressure (429 on overflow)
- [ ] Add structured logging at every node transition: `{node, request_key, status, latency_ms, error_type}`
- [ ] Add per-node and end-to-end latency metrics (even simple in-memory counters/histograms are fine for now)

---

## 4. Dummy data & test plan

Build a small synthetic test harness — no real GeoTIFF/ISRO data needed.

### 4.1 Dummy fixtures to generate

1. **Valid single-image VQA request** — small synthetic multi-band array (e.g. numpy array shaped like a 4-band Sentinel-2 tile) + a simple text query (e.g. "How many buildings are visible?") + `task_type="vqa"`.
2. **Valid bi-temporal change-VQA request** — two synthetic tiles (before/after) of the same shape + query + `task_type="change_vqa"`.
3. **Malformed input (permanent failure case)** — corrupt/truncated image bytes, or missing required bands.
4. **Unsupported sensor type (permanent failure case)** — a `sensor_type` value not in the supported list, to trigger Encoder Compat Check rejection.
5. **Co-registration failure (permanent failure case)** — two synthetic tiles deliberately misaligned/shifted beyond threshold, to trigger the Co-reg Quality Gate.
6. **Slow/hanging backend (transient failure case)** — a mock vision-encoder or fusion-LLM stub that sleeps beyond its timeout budget, to verify timeout enforcement and Error Handler routing.
7. **Flaky backend (transient, retry-success case)** — a mock that fails the first call and succeeds on the second, to verify retry + checkpoint resume works and doesn't redo expensive preprocessing.
8. **Repeated-request case** — the same request key sent twice, to verify checkpoint reuse / idempotency.
9. **Burst load case** — N concurrent requests (start with N = 2x configured queue depth) to verify backpressure (429s) instead of unbounded queuing or crashes.
10. **Circuit breaker case** — force consecutive fusion-LLM failures past the threshold, verify the breaker opens and subsequent requests get the fallback/degraded response instead of hanging.

### 4.2 Assertions per test case

| Case | Must assert |
|---|---|
| Valid VQA / Change-VQA | Completes within total budget (~15s), returns well-formed response schema |
| Malformed input | Fails fast, **no retry attempted**, structured error with reason code |
| Unsupported sensor | Rejected at Encoder Compat Check, no retry, structured reason |
| Co-reg failure | Rejected at Co-reg Quality Gate, no retry, structured reason |
| Slow backend | Node-level timeout fires at configured budget (± small tolerance), routes to Error Handler, does not hang the process |
| Flaky backend | Exactly 1 retry occurs, second attempt succeeds, preprocessing/encoding is **not** redone (verify via checkpoint hit log) |
| Repeated request | Second call resumes from checkpoint, is measurably faster than the first, produces the same result |
| Burst load | Requests beyond queue depth receive a clear rejection, no crash, no unbounded memory growth |
| Circuit breaker | After N failures, breaker opens; subsequent calls short-circuit immediately (fast-fail or fallback), no piling up |

### 4.3 Suggested test structure

```
tests/
  fixtures/
    dummy_data.py          # generates all synthetic tiles/queries above
  test_happy_path.py        # cases 1, 2
  test_permanent_failures.py  # cases 3, 4, 5
  test_transient_and_retry.py # cases 6, 7
  test_idempotency.py       # case 8
  test_load_and_backpressure.py # case 9
  test_circuit_breaker.py   # case 10
```

Use `pytest` with fixtures returning in-memory numpy arrays (no real file I/O needed for dummy testing). Mock the vision-encoder and fusion-LLM service calls with configurable latency/failure injection so timeout, retry, and circuit-breaker behavior can be tested deterministically without real model weights.

---

## 5. Out of scope for this pass

- Real model weight loading/inference correctness (SatMAE/SSL4EO-S12/Prithvi/Qwen 3.5 9B accuracy) — this spec is about resilience/latency around those calls, not the calls' internal correctness.
- Real GeoTIFF parsing edge cases beyond what's needed to exercise the failure paths above.
- Production deployment manifests (Kubernetes/Docker Compose) — can be a follow-up once the in-process resilience layer is verified with dummy data.

---

## 6. Deliverables expected back

1. Updated LangGraph pipeline code with all items in §3 implemented.
2. `tests/` directory per §4.3, all passing against dummy fixtures.
3. A short `RESULTS.md` summarizing observed latencies per node (from the structured logging in §3) under the happy-path and burst-load test cases.
