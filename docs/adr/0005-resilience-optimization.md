# ADR 0005 — Pipeline Resilience & Performance Optimization

* **Date:** 2026-08-29
* **Status:** Accepted
* **Scope:** orchestrator
* **Commit/PR:** `wip`
* **Deciders:** OpenCode (agent)

## Context

LangGraph RS-VLM pipeline had no retry cap, no circuit breaker, no timeout propagation, and no separation between orchestration and GPU model-serving. Spec `docs/satquery-ai-resilience-optimization.md` requires zero-downtime, low-latency, fault tolerance without redesigning agent logic — only wrapping existing nodes.

Constraints: dummy vision (no real weights), Groq rate-limited (must fallback to mock), in-memory for tests (Redis/MinIO optional).

## Decision

Implement resilience layer per §2.1–2.9 with audit fixes:

* **GraphState:** `deadline_ms` (absolute epoch, `new_state` default 0, `input_validator` sets `now+15000`), `request_key` (sorted image hashes + normalized query + `sar_polarization`), `checkpoint_hits`, `retry_policy {max_transient 2, max_confidence 3, max_coreg 2}`, `node_latencies`, `circuit_breaker_state`, `degraded`, `error_type/code`, `_test_inject`.
* **Timeouts:** `core/timeouts.py` budgets (preprocessing 2000ms, vision 4000ms, fusion 6000ms, total 15000ms), `check_deadline_or_raise` before expensive nodes.
* **Retry:** bounded exponential (200ms·2^retry) via `agents/error_handler.py` — 3 for confidence (probabilistic), 2 for infra (timeout/429/OOM), permanent never retries; `pipeline.py` `after_coreg_gate` transient ≤max_coreg else permanent, `after_post_processing` ≤3 confidence else permanent, `after_vision/after_fusion` pure routing with node-side `retry_count` increment (prevents infinite loop).
* **Circuit breaker:** `core/circuit_breaker.py` single `qwen_circuit` for all 3 Qwen calls (router/planner/composer) at `core/llm_client.py:resolve_provider()` + `vision_circuit`/`fusion_circuit` for services; when open returns mock/degraded immediately.
* **Checkpoint:** `core/checkpoint.py` `request_key` → `{preprocessing, vision_encoder}` in-memory dict (Redis note), save after preprocessing/vision, hit resumes without redo.
* **Validation gates:** `encoder_compat`/`coreg_gate` emit `error_type=permanent` + `error_code` (`encoder_modality_mismatch`, `band_count_mismatch`, `coreg_ssim_below_threshold` after retries) and route to `error_handler` (no retry).
* **Service split:** `services/vision_encoder_service.py` + `fusion_llm_service.py` behind `health_live` (process) vs `health_ready` (model warm + circuit closed) per audit; router checks `ready`.
* **Caching:** `core/ttl_cache.py` `tile_cache` (AOI) + `encoder_cache` (modality→encoder) TTL 300/600s.
* **Queue:** `core/queue_gate.py` semaphore `MAX_CONCURRENT_PIPELINES=4` `MAX_QUEUE_DEPTH` → `429` before `BackgroundTasks`.
* **Logging/Metrics:** `core/structured_logging.py` JSON `{node,request_key,status,latency_ms,error_type}` + `core/metrics.py` counters/avg/p95.
* **Benchmark:** `eval/benchmark.py` `BENCHMARK_OVERRIDES {circuit_breaker_enabled False, deadline 60000, max_retries 0}`.
* **Tests:** `tests/fixtures/dummy_data.py` + 6 files covering 10 synthetic cases, `conftest.py` resets singletons, `generate_results.py` auto `RESULTS.md` from `node_latencies`.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Per-call-site circuit breaker (fusion only) | Router/planner still pile on dead Ollama; single breaker at `llm_client` simpler |
| Redis queue for dummy phase | Overkill; in-memory semaphore suffices, note for prod |
| Real sleep in slow-backend tests | CI slow; inject `NodeTimeoutError` directly (audit #8) |

## Consequences

* Positive: fault-tolerant (permanent fast-fail, transient bounded retry, degraded mode), low latency (deadline + checkpoint), zero-downtime split, auditable `node_latencies`.
* Negative: added complexity in `GraphState` + retry bookkeeping; requires careful `retry_count` handling to avoid infinite loop (fixed via node-side increment).
* Follow-ups: tune budgets against real HW, replace in-memory queue/checkpoint with Redis, add K8s manifests.

## Verification

* `orchestrator/.venv python -m pytest tests -q` → `13 passed, 1 skipped` (happy, permanent, transient, idempotency, backpressure, circuit breaker) in ~77s
* `pipeline.ainvoke` happy 5.1s, `request_key` checkpoint reuse, `retry_count` 1 for flaky
* `GET /health/live` + `/health/ready` + `/api/v1/task` with `429` backpressure verified via `TestClient`
