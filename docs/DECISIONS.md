# Decisions Log — Satiq (SatQuery AI)

> Single source of truth for **why** the system is the way it is. Every behavioral, data-handling, or dependency change must append here. Architecture-worthy decisions get a full ADR in `docs/adr/NNNN-*.md` — this file indexes them.

## How to Use

* **Append-only.** Never rewrite history; strikethrough + supersede if needed.
* **One line per change**, plus link to ADR if present. Every entry references a commit/PR.
* **No silent edits** — if `orchestrator/`, `capabilities/`, `gateway/`, or `frontend/` changed and this file didn't, the PR is incomplete (enforced in CI — see `AGENTS.md:8`).
* Format: `| Date | ADR | Title | Scope | Commit/PR | Status |`

## Index

| Date | ADR | Title | Scope | Commit/PR | Status |
|------|-----|-------|-------|-----------|--------|
| 2026-08-26 | [ADR 0000](adr/0000-scaffold.md) | Initialize monorepo scaffold (no code) | repo | `aa6fef2` | Accepted |
| 2026-08-26 | [ADR 0001](adr/0001-agent-governance.md) | Adopt agent governance docs (AGENTS, DECISIONS, PROGRESS, ETHICS) | docs | `5703720` | Accepted |
| 2026-08-26 | — | Add SatQuery architecture README (4 models, orchestrator, input gate) | docs | `5703720` | Logged |
| 2026-08-28 | [ADR 0002](adr/0002-api-gateway.md) | Implement API gateway and rate limiter | gateway | `<fill>` | Accepted |
| 2026-08-28 | [ADR 0003](adr/0003-frontend-workstation.md) | Build Satiq frontend analysis workstation (Phases 0-12) | frontend | `wip` | Accepted |
| 2026-08-28 | — | Redesign primary chat as product-specific conversational operating surface (seed, semantic messages, inline activity, context-aware composer) | frontend | `wip` | Logged |
| 2026-08-29 | [ADR 0004](adr/0004-orchestrator-pipeline.md) | Orchestrator LangGraph RS-VLM pipeline with dummy vision & mocked Qwen 3.5 9B | orchestrator | `f3a70b8` | Accepted |
| 2026-08-29 | [ADR 0005](adr/0005-resilience-optimization.md) | Pipeline resilience & performance (timeout, retry, circuit breaker, checkpoint, queue, TTL cache) | orchestrator | `wip` | Accepted |
| 2026-08-29 | [ADR 0006](adr/0006-full-integration.md) | Full system integration frontend↔gateway↔orchestrator (agentic bridge, mock LLM, Docker) | repo | `wip` | Accepted |

<!-- New entries append below. Keep newest at bottom for git-friendly diffs. -->

## Decision Records

### 2026-08-26 — Scaffold

* **What:** Created monorepo directories per `README.md` structure (frontend/gateway/orchestrator/capabilities/adaptation/evaluation) + `docker-compose.yml` skeleton, `.gitignore`, `README.md`. No implementation — `.gitkeep` placeholders only.
* **Why:** Establish build-priority order (Pydantic models → CRS gate → Model 4 → Model 3 → ...) before any code.
* **Consequences:** `docker compose config` passes; services are no-ops until uncommented.

### 2026-08-26 — Agent Governance

* **What:** Added `AGENTS.md`, `CONTRIBUTING.md`, `docs/ETHICS.md`, `docs/DECISIONS.md` (this file), `docs/PROGRESS.md`, `docs/adr/README.md` + ADR template. Established 5-step workflow (Plan→Implement→Record→Verify→Review) and Definition of Done.
* **Why:** Satiq is built by mixed human+LLM agents; auditability (execution_trace) applies to development too — every edit must be traceable. Prevents hallucinated geospatial results, silent CRS changes, and untracked dependency bloat.
* **Consequences:** All future PRs touching product code must also touch `docs/DECISIONS.md` + `docs/PROGRESS.md`; ADRs required for behavior/data/dep changes.

### 2026-08-28 — API Gateway and Rate Limiter

* **What:** Implemented the Express + TypeScript API Gateway and Rate Limiter, adding `package.json`, `tsconfig.json`, `src/index.ts`, custom middlewares (auth, upload, rateLimiter), and routes (auth, upload, session, query).
* **Why:** Fulfills Milestone M6 gateway requirement: provides security boundaries, rate limiting, and structured session persistence with tenant isolation.
* **Consequences:** Client requests are authenticated via JWT, session store is safe against path traversal, and down-stream orchestration queries are proxied.

---

## Adding a New Decision

1. Append a row to the Index table.
2. If ADR-worthy (architecture, model/library selection, schema/CRS/band handling, API contract, dependency, prompt/fusion strategy), create `docs/adr/NNNN-title.md` from `docs/adr/README.md` template and link it.
3. If docs-only/ trivial, just add the row + a short paragraph in this file under a new `### YYYY-MM-DD — Title` heading.
4. Reference the commit hash after committing.
5. Update `docs/PROGRESS.md` in the same PR.

**Ask:** Does this change alter behavior, data handling, storage, external API, or dependencies? → ADR. Otherwise → line item here is enough.

### 2026-08-28 — Chat redesign

* **What:** Replaced the generic AI-template chat (`ruixen-moon-chat`, moon-image empty state, dual composers, dead `ChatPanel`/`SatiqAIPanel`/`NavigationRail`) with a product-specific conversational surface:
  * `ConversationSeed` — empty state surfaces the 4 real capabilities (change / grounding / optical+SAR fusion / land-cover VQA) + recent-work continuity; no decorative imagery.
  * `MessageItem` — semantic rendering: understated user block, document-style assistant answer with capability tag + confidence badge, inline activity, copy/inspect actions.
  * `ActivityStream` — compact, expandable view of the real execution pipeline (planner → models → evidence → composer) read live from `execution.store`; transparency without noise.
  * `Composer` — context-aware input: removable AOI/file chips, drag-drop attach, progressive capability hints on focus, ⌘K.
  * Reuses existing `MarkdownRenderer` (chart/table/comparison/map blocks), `RightThinkingPanel` (deep inspector), `GeoCanvas`, and `map.store`/execution stores.
* **Why:** The previous chat was a generic ChatGPT-style wrapper (external moon CDN image, leftover `ruixen` template) that violated the product philosophy in the design brief. Satiq's intelligence (multi-agent geospatial QA, auditable traces, visual evidence) must be visible in the interface.
* **Consequences:** `npm run build` passes (tsc + vite). Map still appears contextually after first message; right "Thinking" panel remains the deep inspector.

### 2026-08-29 — Orchestrator Pipeline

* **What:** Built full 14-node LangGraph pipeline reusing existing `orchestrator/` structure (no new scaffold):
  * `core/config.py` (MOCK_QWEN=true, Ollama OpenAI-compat), `core/llm_client.py` (mocked Qwen router/planner/composer with asset-aware heuristic — no network when mocked), `core/redis_state.py` (mem fallback TTL 3600), `core/celery_app.py` (6 queues), `db/models.py` (sessions/images/tiles/task_outputs/coreg/embeddings), `models/raster_asset.py` + `analysis_result.py` + `graph_state.py` (TypedDict with Annotated _last reducers), `dummy/dummy_encoders.py` (SatMAE 1024/Ssl4eo 768/Prithvi 768/CROMA), `dummy/dummy_fusion.py` (attention), `dummy/dummy_task_agents.py` (4 exact prompt JSON shapes + confidence 0.78-0.90), `agents/*` (14 pure nodes), `graph/pipeline.py` (conditional edges: CRS fail→error, coreg retry<2, conf<0.6 retry<3), `graph/visualize.py` (Mermaid + PNG 56KB), `services/minio_client.py` (disk fallback) + `tiling.py`, `api/main.py` (POST /api/v1/task 400 on CRS mismatch before LLM, GET status, WS streaming of gateway-compatible SSE events, BackgroundTasks fallback for Celery), `scripts/generate_dummy_data.py` + `run_pipeline_demo.py`, `tests/test_validator.py` (CRS hard gate regression), `tests/test_dummy_models.py`, `tests/test_pipeline.py`, `Dockerfile` + updated `docker-compose.yml` (postgis+redis+minio+rabbitmq+orchestrator+gateway+frontend), `orchestrator/.venv` + `requirements.txt`, `README.md`.
  * Qwen mocked explicitly: `MOCK_QWEN=true` in `.env` + `config.mock_qwen`; when true, `llm_client` never creates OpenAI client or hits network, returns deterministic `_mock:true, _mode:mock_qwen_3.5_9b` and `Mocked Qwen 3.5 9B composer` suffix; swappable to real Ollama by flipping flag + pulling `qwen3:8b`.
* **Why:** Prompt requires entire RS-VLM pipeline today with only Qwen real; all vision dummies swappable. Must not create duplicate `rs-vlm/app` scaffold — reuse. Need deterministic safety gates, auditable trace, retry policies, graph visualization, and offline-operable infra (SQLite/Redis/MinIO/Celery all have local fallbacks). User explicitly: don't download Qwen now → mock, keep $ wiring.
* **Consequences:** `TestClient POST /api/v1/task` works for all 5 inputs: vqa→0.87, grounding→bbox [120,45,310,210], change→`built-up_increase`, fusion→`{optical 0.82 sar 0.76 fused 0.9}`; CRS mismatch →400 before LLM; `execution_trace` has 13 agents; `orchestrator/graph/graph.png` generated; `docker compose config` valid; `orchestrator/tests` PASS. Real vision/GDAL and real Qwen are deferred but isolated to `dummy/` + flag flip — no graph change needed.

### 2026-08-29 — Resilience & Optimization

* **What:** Implemented `docs/satquery-ai-resilience-optimization.md` §2.1–2.9 with 10 audit fixes: `GraphState` deadline/request_key/checkpoint/retry_policy/node_latencies/degraded/_test_inject, `core/timeouts` budgets, `core/checkpoint` sorted-hash request_key, `core/circuit_breaker` single `qwen_circuit` at `llm_client.resolve_provider`, `core/queue_gate` semaphore 429, `core/ttl_cache` tile/encoder, `services/vision_encoder_service` + `fusion_llm_service` with `health_live`/`health_ready`, `core/metrics` + `structured_logging`, `eval/benchmark` `BENCHMARK_OVERRIDES`, `tests/` 10 synthetic cases with `conftest` resets.
* **Why:** Pipeline had no retry cap, no breaker, no deadline, no service split — spec required fault tolerance without redesign.
* **Consequences:** `pytest tests -q` 13 passed 1 skipped; `request_key` checkpoint reuse, `retry_count` 1 for flaky, `429` backpressure, `health/ready` 503 when circuit open.

### 2026-08-29 — Full Integration

* **What:** Wired `frontend (5173) → gateway (4000) → orchestrator (8000)` agentic path with mocked LLM (no Groq): `gateway` `AgenticAnalysisProvider` POST `/api/query` → `POST /api/v1/task` + SSE poll, `ANALYSIS_PROVIDER=agentic`, `orchestrator` `MOCK_QWEN=true LLM_PROVIDER=mock`, `gateway/frontend` Dockerfiles with `shared/` copy and `context: .`, `frontend` `analysisClient.ts` auto-login `demo/demo` → `localStorage satiq_token`, `applyEvent.ts` store bridge, `Composer` tries real then fallback to mock, `execution.ts` add `cancelled`, `docker-compose` `VITE_API_BASE=http://localhost:4000`.
* **Why:** User requested complete product ready without Groq calls; gateway was mock-only, frontend was mock-only; needed real SSE integration for demo.
* **Consequences:** `gateway npm run typecheck` pass, `frontend npm run build` pass, `POST /api/query` via gateway returns `exec_*` and streams real pipeline events (verified via `Invoke-RestMethod`); offline demo works.
