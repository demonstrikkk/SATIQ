# ADR 0004 — Orchestrator LangGraph RS-VLM Pipeline with Dummy Vision & Qwen 3.5 9B

* **Date:** 2026-08-29
* **Status:** Accepted
* **Scope:** orchestrator / capabilities / registry / graph
* **Commit/PR:** wip
* **Deciders:** OpenCode (Muse Spark)

## Context

Satiq requires a production-ready agentic pipeline where only Qwen 3.5 9B is real (via Ollama OpenAI-compatible) and all vision encoders/fusion/task heads are dummy but return realistic-shaped JSON. Previous state was scaffold only (`.gitkeep`s) with frontend/gateway mocked. Need deterministic gates (CRS hard fail), auditable trace, retry policies, and swappability: when real SatMAE/SSL4EO/Prithvi/CROMA checkpoints arrive, only `orchestrator/dummy/` changes.

Constraints: Python 3.11, no extra scaffold folders (reuse `orchestrator/`), Ollama already installed but model not pre-downloaded (must gracefully fallback), need graph visualization of node connections, need FastAPI + Redis/MinIO/Celery with local fallbacks so pipeline works without Docker.

## Decision

Build the full 14-node LangGraph pipeline reusing existing structure:

**Folder mapping (no new scaffold):** `orchestrator/` is `app/` from prompt — added `orchestrator/core/`, `orchestrator/dummy/`, `orchestrator/graph/`, `orchestrator/services/`, `orchestrator/api/`, `orchestrator/scripts/`, `orchestrator/tests/` alongside existing `models/`, `ingestion/`, `planner/`, `registry/`, `engine/`, `evidence/`, `composer/`, `helpers/`.

**Stack:** `FastAPI 0.110.2 + uvicorn`, `langgraph 0.2.39`, `langchain 0.2.6`, `langchain-openai 0.1.8`, `openai`, `pydantic 2.13`, `SQLAlchemy 2.0 + asyncpg + aiosqlite`, `redis 8`, `minio`, `numpy`, `pillow`, `httpx`, `python-multipart`.

**State:** `GraphState` TypedDict with `Annotated[..., _last]` reducers so LangGraph LastValue channels work sequentially. Every agent is pure: `(GraphState) -> GraphState`, only reads/writes state, never calls another agent, logs to `execution_trace`.

**Agents (14):**
1 Input Validator (deterministic CRS hard gate) — 2 Router (Qwen via Ollama, heuristic fallback asset-aware) — 3 Planner (Qwen JSON StepPlan) — 4 Encoder Selector (rule-based) — 5 Encoder Compat Gate — 6 Preprocessing (tiling + dummy co-reg SSIM/residual) — 7 Co-reg Gate (SSIM≥0.75) — 8 Vision Encoder (dummy SatMAE/SSL4EO/Prithvi/CROMA) — 9 Fusion (dummy attention) — 10 Task Agent (routes to 4 dummy task fns) — 11 Tile Manager (Redis tracker) — 12 Post-Processing (confidence gate <0.6 + chart) — 13 Error Handler — 14 Response Composer (Qwen fuse).

**LangGraph (`orchestrator/graph/pipeline.py`):**
```
START → input_validator → (router | error) → planner → preprocessing → encoder_selector → encoder_compat → (coreg_gate | error) → coreg_gate → (vision_encoder | preprocessing(retry<2) | error) → vision_encoder → fusion → task_agent → (tile_manager | error) → tile_manager → post_processing → (task_agent(retry conf<0.6 <3) | response_composer | error) → END
```
All edges are deterministic; `build_graph().get_graph().draw_mermaid_png()` produces `graph.png`.

**Dummy models (`orchestrator/dummy/`):**
- `run_satmae` 1024-d, `run_ssl4eo` 768-d, `run_prithvi` 768-d, `run_croma` — deterministic per tile_id via seeded RNG.
- `run_fusion` — attention/concat, confidence derived from query length.
- `dummy_vqa` (open/closed with answer_short), `dummy_grounding` (bbox_xyxy + normalized + confidence), `dummy_change_vqa` (change_categories + answer_text), `dummy_optical_sar_fusion` (per_modality_confidence + class_map_rle) — exact JSON from prompt plus `vqa_chart`/`fusion_chart` helpers. Confidence clamped [0,1], bboxes within bounds.

**LLM (`core/llm_client.py`):** OpenAI client pointed at `QWEN_BASE_URL=http://localhost:11434/v1` with `QWEN_MODEL=qwen3.5:9b`. If Ollama unavailable (current state), heuristic fallback: asset-aware router detects `optical+sar` pair → fusion even when query lacks "sar"; change → change_vqa; grounding → bbox. Planner/composer similarly fallback, always returns valid JSON. No hard-coded weights — dummies are swappable.

**FastAPI (`api/main.py`):** `POST /api/v1/task` validates CRS before LLM (400 on mismatch), creates `session_id`, enqueues `run_pipeline` via `BackgroundTasks` (Celery queues defined in `core/celery_app.py` but executed in-process for local dev). Updates in-memory `EXECUTIONS` + Redis pub/sub + WS fanout. Emits gateway-compatible SSE events: `query_started → input_done → planner_done → execution_started → model_started/progress/done → evidence_done → composer_started → thinking_delta → answer_delta → final_answer → query_completed`. `GET /api/v1/task/{id}` returns status + result + trace. `WS /ws/task/{id}` replays buffered events then subscribes. Persist final JSON to MinIO fallback `orchestrator/storage/rs-outputs/`.

**Infra fallbacks:** Postgres → SQLite `satiq.db` if `DATABASE_URL` missing; Redis → in-memory dict with TTL simulation; MinIO → local disk `orchestrator/storage/<bucket>/`; Celery → FastAPI BackgroundTasks. This satisfies "docker-compose brings up 5 services but pipeline works without them" requirement.

**Observability:** Every node pushes `execution_trace` with `agent,status,latency_ms,detail`; structured logs via `structlog` pattern; Prometheus metrics stub ready.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| New `rs-vlm/app` scaffold as in prompt | Duplicates existing `orchestrator/` layout from README; AGENTS.md says reuse, not duplicate |
| Full microservices per agent | Overkill for hackathon; LangGraph single service with deterministic state channel is smallest responsible |
| Separate LangGraph for each task type | Would duplicate validator/router/planner; single graph with conditional edges covers all 5 inputs via routing |
| Real rasterio/GDAL in preprocessing now | Heavy system dep; dummy tiling keeps pipeline testable without gdal install, real code isolated to `services/tiling.py` for later swap |
| Require Qwen download before any test | Violates "don't download model for now"; fallback heuristic keeps pipeline verifiable offline and is auditable (logged as heuristic) |

## Consequences

* Positive: `POST /api/v1/task` → LangGraph → WS streaming works for all 4 task types with correct-shaped outputs; CRS mismatch rejected before LLM (safety-critical); graph.png/mmd generated for audit; dummy models swappable without graph change; local venv `orchestrator/.venv` created and verified.
* Negative / risks: Vision is fake (no real geospatial inference) — must not be presented as real evidence; marked as dummy in trace/composer note. Ollama fallback is heuristic, not LLM-quality routing (will improve when Qwen pulled). Real co-reg (SSIM via rasterio) and vector DB (pgvector) deferred — dummy values used. Bundle: `rasterio`/`gdal` not in venv yet — needs system install for real GeoTIFF.
* Follow-ups: Pull `qwen3:8b` via Ollama when authorized and set `QWEN_MODEL`; install `rasterio`+`gdal` and enable real tiling; add Alembic migrations; wire gateway `query.ts` provider to orchestrator `http://orchestrator:8000`; add CI check `docker compose config`.

## Verification

* `orchestrator/.venv` created, `pip install` verified: `fastapi 0.110.2, langgraph 0.2.39, pydantic 2.13`
* Unit: `python orchestrator/tests/test_validator.py` → PASS (CRS mismatch rejected, valid passes)
* Unit: `python orchestrator/tests/test_dummy_models.py` → PASS (4 task shapes + encoder dims)
* Pipeline: `TestClient POST /api/v1/task` for vqa → `completed` task `vqa` confidence 0.87; change_vqa → `change_categories ["built-up_increase"]`; fusion → `per_modality_confidence {optical 0.82 sar 0.76 fused 0.9}`; grounding → `bbox_xyxy [120,45,310,210]`; CRS mismatch POST → `400`
* Graph: `python orchestrator/graph/visualize.py` → `graph.png` 56KB, `graph.mmd` valid Mermaid flowchart
* Compose: `docker compose config` → valid (postgres, redis, minio, rabbitmq, orchestrator, gateway, frontend)
* Fallback: with Ollama not running, logs `[qwen router fallback] Connection error.` and uses heuristic — pipeline still completes, trace shows `heuristic fallback`.

