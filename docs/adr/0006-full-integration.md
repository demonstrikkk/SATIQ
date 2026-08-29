# ADR 0006 — Full System Integration (Frontend↔Gateway↔Orchestrator)

* **Date:** 2026-08-29
* **Status:** Accepted
* **Scope:** repo (gateway, frontend, orchestrator, compose)
* **Commit/PR:** `wip`
* **Deciders:** OpenCode

## Context

Pipeline (ADR 0004+0005) was validated in isolation via `TestClient`; gateway still used `MockAnalysisProvider`, frontend used `simulateAnalysisQuery` mock, orchestrator called Groq (`MOCK_QWEN=false`) hitting rate limits. Need complete product ready with mocked LLM (no Groq calls) and real agentic path.

## Decision

* **Orchestrator mock:** `orchestrator/.env` `MOCK_QWEN=true` `LLM_PROVIDER=mock` (no Groq network); benchmark overrides already disable circuit breaker.
* **Gateway agentic bridge:** new `gateway/src/analysis/providers/agentic-analysis.provider.ts` — `POST /api/query` → `POST http://orchestrator:8000/api/v1/task` (maps `asset_ids`/`spatial_refs` → `image_ids`/`assets`), then polls `GET /api/v1/task/:id` / SSE `GET /api/query/:id/stream` via `fetch` with JWT, translates `ExecutionEvent` to shared contracts, emits `error` on `429`/`orchestrator_unreachable`. `analysis-provider.ts` now returns `AgenticAnalysisProvider` when `ANALYSIS_PROVIDER=agentic`.
* **Env:** `gateway/.env` + `.env.example` `ANALYSIS_PROVIDER=agentic`, `docker-compose.yml` `gateway` `ANALYSIS_PROVIDER=agentic` + `CORS_ORIGIN`, `frontend` `VITE_API_BASE=http://localhost:4000`.
* **Docker:** `gateway/Dockerfile` + `frontend/Dockerfile` with `shared/` copy (context `.`), `docker-compose.yml` `build: {context: ., dockerfile: …}` + `frontend` `VITE_API_BASE` arg.
* **Frontend real client:** `frontend/src/lib/analysisClient.ts` — auto-login `POST /api/auth/login` `demo/demo` → `localStorage satiq_token`, `POST /api/query`, `GET /stream` with `Authorization`, `frontend/src/lib/applyEvent.ts` central store updater (used by both mock and real), `Composer.tsx` `handleSend` tries `executeRealAnalysis` then falls back to `simulateAnalysisQuery`, `auto-dequeue` same.
* **Schema:** `frontend/src/schemas/execution.ts` add `cancelled` to `ExecutionEventSchema`.
* **Verification:** `gateway npm run typecheck` pass, `frontend npm run build` pass (vite 2559 modules, chunk warning only), `orchestrator` `POST /api/v1/task` + `GET /health/ready` manual, `POST /api/query` via gateway → `exec_*` + stream (tested via `Invoke-RestMethod`).

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Keep mock gateway + mock frontend indefinitely | No real pipeline evidence; integration untested |
| Direct frontend → orchestrator (bypass gateway) | Breaks auth/tenancy, CORS, session isolation (`AGENTS.md:6`) |

## Consequences

* Positive: end-to-end `frontend (5173) → gateway (4000) → orchestrator (8000) → dummy vision + mocked Qwen` with JWT, SSE, backpressure 429, degraded mode; offline demo works without Groq/Ollama.
* Negative: `VITE_API_BASE` baked at build time for Docker; needs rebuild on URL change.
* Follow-ups: replace disk `upload/` with MinIO, add WS for faster streaming, code-split frontend chunk >1200KB.

## Verification

* `gateway npm run typecheck` → pass
* `frontend npm run build` → pass
* `orchestrator/.venv pytest tests/test_happy_path` → pass 6.4s
* Manual `POST http://127.0.0.1:8000/api/v1/task` → `sess_*` + `GET /health/ready` `closed` + `GET /api/v1/task/:id` polling; `POST http://127.0.0.1:4000/api/query` via gateway with `ANALYSIS_PROVIDER=agentic` → `exec_*` running
