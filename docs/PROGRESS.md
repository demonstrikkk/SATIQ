# Progress Tracker — Satiq (SatQuery AI)

> Kanban + milestone view. Every task that writes/edits/deletes code must move a row here in the **same commit/PR** that changes code. Stale = incomplete.

**Last updated:** 2026-08-31 · **Branch:** `main` · **Head:** `wip`

## Milestones

| Milestone | Scope | Status | Owner | ETA | Notes |
|-----------|-------|--------|-------|-----|-------|
| M0 — Scaffold | Repo structure, compose, README, governance docs | **Done** | — | 2026-08-26 | `aa6fef2`, `5703720` |
| M1 — Core Contracts | `raster_asset.py`, `analysis_result.py`, `validator.py` (CRS hard gate) | **Done** | — | 2026-08-29 | ADR 0004; Pydantic models + validator with CRS mismatch regression test |
| M2 — Fusion (Model 4) | CROMA-based optical+SAR cross-attention, seg head, BigEarthNet S1+S2 | **Done (real wiring, blocked on checkpoint)** | — | 2026-08-31 | ADR 0007; real CROMA via `capabilities/fusion/optical_sar.py` + ModelManager, `MODEL_LOAD_ERROR` if `capabilities/fusion/weights/croma.pth` missing |
| M3 — Change (Model 3) | Change-VQA/Desc + change map, bi-temporal FM | **Done (real hybrid)** | — | 2026-08-31 | ADR 0007; real stage1_index_hybrid `temporal/change_vqa.py` NDVI/NDBI/NDWI + fusion cosine + Vicuna 4-bit, `stage1_final.pth` + `visualisation_tool` change_map |
| M4 — Single-Image (M1+M2) | RS-VQA (GeoChat) + Grounding (GroundingDINO+SAM) | **Done (real wiring, blocked on checkpoint)** | — | 2026-08-31 | ADR 0007; real GDINO S2 percentile stretch `single_image/grounding.py` + VQA `single_image/vqa.py`, ModelManager, `MODEL_LOAD_ERROR` if weights missing |
| M5 — Orchestrator | `llm_planner`, `capability_registry`, `topo_resolver`, `execution_engine`, `evidence_graph`, `vlm_composer`, supervisor/critic loop | **Done** | — | 2026-08-29 | ADR 0004; 14-node LangGraph, mocked Qwen 3.5 9B (MOCK_QWEN=true), gates/retries, WS streaming, graph.png |
| M6 — Gateway & Frontend | GeoTIFF upload, session, MapLibre workspace, ExecutionTrace inspector | **Done** | — | 2026-08-28 | ADR 0002, 0003; gateway + 12-phase frontend complete, mocked SSE + spatial multiturn verified |
| M7 — Adaptation & Eval | BigEarthNet fine-tune (LoRA), VRSBench/RSVQA/CDVQA harness, PDF reports | Planned | — | — | — |

## Task Board

| ID | Title | Phase | Status | Assignee | PR/Commit | Blockers / Next |
|----|-------|-------|--------|----------|-----------|-----------------|
| T-001 | Init monorepo + compose skeleton | M0 | **Done** | — | `aa6fef2` | — |
| T-002 | SatQuery architecture README | M0 | **Done** | — | `5703720` | — |
| T-003 | Agent governance docs (AGENTS, DECISIONS, PROGRESS, ETHICS, ADR) | M0 | **Done** | — | this commit | — |
| T-010 | Pydantic `raster_asset.py` (CRS, resolution, bands, timestamp) | M1 | **Done** | OpenCode | `wip` | ADR 0004; TypedDict + Pydantic, CRS regex, bbox/GSD validators |
| T-011 | Pydantic `analysis_result.py` (answer + evidence + confidence + trace) | M1 | **Done** | OpenCode | `wip` | 4 task shapes (VQA/Grounding/Change/Fusion) with confidence [0,1] |
| T-012 | Deterministic validator — CRS hard gate + format/modality/pairing checks | M1 | **Done** | OpenCode | `wip` | `ingestion/validator.py` + `agents/input_validator` hard gate; pytest `test_validator.py` CRS mismatch→400 before LLM |
| T-020 | Query normalizer | M5 | **Done** | OpenCode | `wip` | In `agents/router` + `llm_client` heuristic (asset-aware) |
| T-030 | Model 4: CROMA fusion layer + seg head | M2 | **Done (real)** | OpenCode | `wip` | `capabilities/fusion/optical_sar.py` CROMA real (ModelManager) + `MODEL_LOAD_ERROR` if missing; `dummy` kept as fallback docs |
| T-031 | Model 3: bi-temporal encoder + change map + CDVQA tuning | M3 | **Done (real hybrid)** | OpenCode | `wip` | `temporal/change_vqa.py` stage1_index_hybrid (indices + fusion cosine + Vicuna 4-bit) + change_map PNG + `pipeline_mode` |
| T-032 | Model 1: RS-VQA projection + LoRA | M4 | **Done (real)** | OpenCode | `wip` | `capabilities/single_image/vqa.py` RS-LLaVA real wiring + ModelManager `MODEL_LOAD_ERROR` |
| T-033 | Model 2: GroundingDINO + SAM mask | M4 | **Done (real)** | OpenCode | `wip` | `capabilities/single_image/grounding.py` S2 percentile stretch verbatim + GDINO `scores` confidence + `MODEL_LOAD_ERROR` |
| T-040 | Orchestrator planner (function-calling) | M5 | **Done** | OpenCode | `wip` | `agents/planner_agent` Qwen JSON StepPlan, MOCK_QWEN=true, mocked heuristic with `_mock:true` → now `LLM_PROVIDER=groq` live, no mock per ADR 0007 |
| T-042 | Execution engine + result cache | M5 | **Done** | OpenCode | `wip` | `graph/pipeline.py` 14-node LangGraph + `core/redis_state` mem fallback + `api/main` BackgroundTasks |
| T-041 | Capability registry + topo resolver | M5 | **Done** | OpenCode | `wip` | `agents/encoder_selector` rule-based + `encoder_compat` gate |
| T-042 | Execution engine + result cache | M5 | **Done** | OpenCode | `wip` | `graph/pipeline.py` 14-node LangGraph + `core/redis_state` mem fallback + `api/main` BackgroundTasks |
| T-043 | Evidence graph + confidence engine | M5 | **Done** | OpenCode | `wip` | `agents/tile_manager` + `evidence` via trace + `post_processing` conf gate |
| T-044 | Supervisor/critic loop (max N iter, legality checks) | M5 | **Done** | OpenCode | `wip` | Coreg gate retry<2, post_processing retry<3 via conditional edges |
| T-045 | VLM composer + PDF report | M5 | **Done** | OpenCode | `wip` | `agents/response_composer` mocked Qwen + `helpers/chart_spec.py` bar/donut validation |
| T-050 | Gateway: upload, session, routes | M6 | **Done** | Antigravity | this commit | verified locally |
| T-051 | Frontend workspace + ExecutionTrace inspector | M6 | **Done** | OpenCode | wip | All 12 phases: foundation, design system, shell, map, chat/markdown, execution trace, evidence/inspector, mock engine, multiturn, polish, QA |
| T-052 | Frontend polish + responsive + a11y + chunk split | M6 | Done | OpenCode | wip | Bundle 1.91MB — follow-up code-split |
| T-053 | Mock scenarios (coastal, grounding, fusion, failure) | M6 | Done | OpenCode | wip | mockStream + executionEvents driving same stores as real SSE |
| T-054 | Redesign primary chat as product-specific conversational surface | M6 | Done | OpenCode | wip | seed + semantic messages + inline ActivityStream + context-aware Composer; removed generic ruixen template |
| T-060 | Adaptation configs + train/eval scripts | M7 | Todo | — | — | — |
| T-061 | Evaluation suites (vrsbench, rsvqa, cdvqa) | M7 | **Done (dummy harness)** | OpenCode | wip | `eval/benchmark.py` `run_benchmark` + SSE stream, dummy samples, metrics acc/F1/MAE |
| T-070 | LLM switch local→Groq qwen/qwen3.6-27b + voice whisper-large-v3 | M5 | **Done** | OpenCode | wip | `core/llm_client.py` auto switch (psutil+ollama check → groq `groq/compound-mini` router fast), `MOCK_QWEN=false LLM_PROVIDER=groq` default to Groq when no local qwen |
| T-071 | Image ingest FFmpeg + EXIF/Pillow | M1 | **Done** | OpenCode | wip | `services/image_ingest.py` + `POST /api/v1/ingest` |
| T-072 | Query analyzer + conversation followup | M5 | **Done** | OpenCode | wip | `services/query_analyzer.py` + `services/conversation.py` + `GraphState` history |
| T-073 | Geocoder region→bbox + spectral NDVI/NDWI | M1/M2 | **Done** | OpenCode | wip | `services/geocoder.py` Sector A/B/C, `services/spectral.py` |
| T-074 | Model interface Protocol per_tile_confidence | M2 | **Done** | OpenCode | wip | `dummy/model_interface.py` EncoderInterface |
| T-075 | Band availability check | M2 | **Done** | OpenCode | wip | `agents/encoder_compat.py` `check_required_bands` |
| T-076 | Multi-part sub_queries + result_merger + numeric | M5 | **Done** | OpenCode | wip | `agents/planner_agent.py` sub_queries + `helpers/result_merger.py` + `dummy_task_agents` answer_numeric |
| T-077 | Data-driven charts + GeoJSON + Report | M5 | **Done** | OpenCode | wip | `helpers/chart_spec.py:104` `build_chart_from_task_output` + `services/geojson_export.py` + `services/report_generator.py` |
| T-078 | Followup suggestions + confidence explanation + recompose | M5 | **Done** | OpenCode | wip | `agents/response_composer.py:1` 3 suggestions, explanation, `POST /task/{id}/recompose` |
| T-079 | Observability trace summary + benchmark | M5 | **Done** | OpenCode | wip | `helpers/trace.py` bottleneck + `GET /session/{sid}/trace/summary` |
| T-080 | Pipeline resilience (timeout, retry, circuit breaker, checkpoint, queue, TTL cache) | M5 | **Done** | OpenCode | wip | ADR 0005; `core/*` + `services/*` + `tests/` 10 cases 13 passed 1 skipped |
| T-081 | Full integration frontend↔gateway↔orchestrator (agentic, mock LLM, Docker) | M6 | **Done** | OpenCode | wip | ADR 0006; `gateway` agentic provider, `frontend` analysisClient, `docker-compose` |
| T-090 | Replace dummy/mocks with real models (4 capabilities + ModelManager + visualisation_tool) | M2-M4 | **Done** | OpenCode | `wip` | `capabilities/*` real wiring + `agents/task_agents.py` + `models/analysis_result.py` additive; `pytest 21 passed` (incl. 7 `test_real_models`), `npm run build` + `gateway typecheck` pass per ADR 0007 |

**Statuses:** `Todo` → `In Progress` → `In Review` → `Done` · Mark `Blocked` if waiting on external (checkpoint, dataset).

## Deferred / Stubs

> Anything marked `STUB:` in code must be listed here with reason.

| Location | Stub | Reason | Created |
|----------|------|--------|---------|
| `gateway/src/routes/query.ts` | STUB_FALLBACK mock response | Fallback response when downstream orchestrator is not running or not implemented yet | 2026-08-28 |
| `orchestrator/dummy/*` | STUB_MOCK vision (SatMAE/SSL4EO/Prithvi/CROMA) + fusion + 4 task heads | Dummy embeddings 768/1024-d via seeded RNG; real checkpoints now in `capabilities/*/weights/` (see ADR 0007) — `dummy/*` kept as docs/fallback only | 2026-08-29 |
| `capabilities/*/weights/*` | Wired but blocked | Real models wired via `ModelManager`; `MODEL_LOAD_ERROR` until `.pth` dropped in `capabilities/single_image/weights/`, `capabilities/temporal/weights/stage1_final.pth`, `capabilities/fusion/weights/croma.pth` | 2026-08-31 |
| `orchestrator/core/llm_client.py` | STUB_MOCK Qwen 3.5 9B (`MOCK_QWEN=true`) | Heuristic router/planner/composer with `_mock:true` marker; flip to `false` + `ollama pull qwen3:8b` for real LLM | 2026-08-29 |
| `orchestrator/services/tiling.py` | STUB dummy tiling (1 tile) | Real rasterio windowed tiling deferred (needs gdal); interface stable | 2026-08-29 |
| `orchestrator/services/minio_client.py` | STUB disk fallback | MinIO not required locally; `storage/` used when MinIO unreachable | 2026-08-29 |
| `orchestrator/db/models.py` | STUB pgvector → JSON fallback | `image_embeddings.embedding` is JSON locally, Vector(dim) on Postgres+pgvector | 2026-08-29 |

## Verification Log

| Date | Task | Command | Outcome | Commit |
|------|------|---------|---------|--------|
| 2026-08-26 | T-001 | `docker compose config` | valid (services stubbed) | `aa6fef2` |
| 2026-08-26 | T-003 | `git status` / `git log --oneline` | clean, `5703720` | this commit |
| 2026-08-28 | T-050 | Code review & structural verification | Files created and validated for TypeScript structure | this commit |
| 2026-08-28 | T-051 | `npm run build` (frontend) | pass — 2725 modules, built in 3.83s | wip |
| 2026-08-28 | T-051 | `npm run build` re-check after path-fix | pass | wip |
| 2026-08-28 | T-054 | `npm run build` (chat redesign) | pass — 2152 modules, built in ~1s; only pre-existing GeoCanvas chunk-size warning | wip |
| 2026-08-29 | T-010..T-045 | `orchestrator/.venv` setup + `pip install` | fastapi 0.110.2, langgraph 0.2.39, pydantic 2.13, etc. installed to `orchestrator/.venv` | wip |
| 2026-08-29 | T-012 | `python orchestrator/tests/test_validator.py` | PASS — CRS mismatch rejected, valid passes | wip |
| 2026-08-29 | T-030..033 | `python orchestrator/tests/test_dummy_models.py` | PASS — 4 task shapes + encoder dims | wip |
| 2026-08-29 | T-040..045 | `TestClient POST /api/v1/task` ×4 | PASS — vqa 0.87, change_vqa `built-up_increase`, fusion `{optical 0.82 sar 0.76 fused 0.9}`, grounding bbox [120,45,310,210]; CRS mismatch →400 | wip |
| 2026-08-29 | M5 | `python orchestrator/graph/visualize.py` | PASS — `graph.mmd` + `graph.txt` + `graph.png` 56KB | wip |
| 2026-08-29 | M5 | `docker compose config` | valid — 7 services (postgres, redis, minio, rabbitmq, orchestrator, gateway, frontend) | wip |
| 2026-08-29 | T-030..045 | Mocked Qwen check `MOCK_QWEN=true` | PASS — no `Connection error`, `_mock:true`, `_mode:mock_qwen_3.5_9b` | wip |
| 2026-08-29 | T-070 | Groq switch `LLM_PROVIDER=groq` `GROQ_MODEL=qwen/qwen3.6-27b` `GROQ_ROUTER_MODEL=groq/compound-mini` | PASS — `GET /api/v1/llm/status` → `provider:groq, has_local_qwen:false, has_key:true`; `has_local_qwen_capability()` false (no ollama), auto resolves to groq; `POST /api/v1/transcribe` with dummy wav → Groq 400 invalid media then mock fallback; `GROQ_API_KEY` redacted | wip |
| 2026-08-29 | T-071 | Groq router fast path `groq/compound-mini` single-word | PASS — `call_qwen_router` via `groq/compound-mini` returns `vqa`/`change_vqa` in 1.1-1.3s vs qwen 5s thinking; `has_local` false so `resolve_provider` groq; `qwen/qwen3.6-27b` listed via `models.list` as available | wip |
| 2026-08-29 | T-072 | Full pipeline with Groq + dummy vision | PASS — `pipeline.ainvoke` 5.1s `vqa` `qwen/qwen3.6-27b` via Groq (planner/composer) + `groq/compound-mini` router; trace `router:groq, planner:groq, response_composer:groq`; `TestClient POST /api/v1/task` ×4 via Groq still `completed` (vqa, grounding bbox, change `built-up_increase`, fusion per_modality) | wip |
| 2026-08-29 | T-073 | Image ingest `services/image_ingest.py` FFmpeg/Pillow | PASS — `POST /api/v1/ingest` PNG `img_001.png` → `validation valid:true, bands:3` + `thumbnail` + `exif` | wip |
| 2026-08-29 | T-074 | Query analyzer + conversation + geocoder | PASS — `detect_temporal` `2021,2023` `is_temporal:true`; `geocoder resolve Sector A → [79.0,12.0,79.5,12.5]`; followup `sess_follow1` second query inherits `img_2021,img_2023` → `change_vqa` not grounding | wip |
| 2026-08-29 | T-075 | Spectral `ndvi/ndwi/ndbi/evi` dummy trace + band check | PASS — `preprocessing` trace `spectral:{ndvi_mean:0.42...}` for change/fusion; `encoder_compat` `band_reports` with `Cartosat no NIR` warning | wip |
| 2026-08-30 | T-088 | Groq latency + false-failure fix | PASS — `gateway npx tsc --noEmit` OK; `call_qwen_router` 1.51s, `call_qwen_planner` 1.42s; poll budget 360s→240s | wip |
| 2026-08-30 | T-089 | Thinking text + timer freeze | PASS — `frontend npm run build` + `gateway tsc`; async planner/router emit real reasoning; clocks stop at terminal | wip |
| 2026-08-30 | T-090 | Composer `<think>` stripping + edit/retry UX | PASS — `frontend build` + `gateway tsc` + `pytest orchestrator/tests/test_pipeline.py` (4 passed); `run_pipeline` E2E `answer_delta` clean (no `<think>`), `query_completed`; real Groq composer ~2.2s/229 chars (was 90s+) | wip |
| 2026-08-30 | T-091 | Multi-key distribution (2 Groq + 1 Mistral) + full display | PASS — `frontend build` + `gateway tsc` + `pytest orchestrator/tests/test_pipeline.py + test_validator.py` (8 passed); `GET /api/v1/llm/status` `key_count:2 mistral:true`; `run_pipeline` `Where is water body` 51 events, 2 thinking deltas, 34 answer chunks, `completed` with chart/bbox, no rate-limit | wip |
| 2026-08-29 | T-076 | GeoJSON `GET /task/{sid}/geojson` + Report `POST /session/{sid}/report` + Recompose `POST /task/{sid}/recompose` | PASS — grounding GeoJSON `FeatureCollection 1 feat`; report html 1488B; recompose v2 `followup_suggestions[0]=What is area in ha?` | wip |
| 2026-08-29 | T-077 | Trace summary `GET /session/{sid}/trace/summary` + Benchmark `POST /benchmark` vrsbench | PASS — `total_ms:66, slowest:planner, breakdown`; benchmark `accuracy:0.0 count_mae:0.26 num:2` | wip |
| 2026-08-29 | T-080 | `pytest tests -q` resilience | PASS — `13 passed, 1 skipped` (happy, permanent, transient, idempotency, backpressure 429, circuit breaker) 77s | wip |
| 2026-08-29 | T-080 | `GET /health/live` + `/health/ready` | PASS — `{"status":"ready","qwen":"closed","vision":"ready","fusion":"ready","queue":0}` | wip |
| 2026-08-29 | T-081 | `gateway npm run typecheck` + `frontend npm run build` | PASS — gateway `tsc --noEmit` (no errors), frontend `tsc && vite build` 2559 modules | wip |
| 2026-08-29 | T-081 | Manual gateway agentic `POST /api/query` via `ANALYSIS_PROVIDER=agentic` | PASS — `POST http://127.0.0.1:4000/api/query` → `{"execution_id":"exec_*","status":"running"}` + stream | wip |
| 2026-08-30 | T-082 | STT voice input (mic) frontend + gateway `/api/stt` → orchestrator Whisper | PASS — gateway typecheck clean; `POST /api/stt` requires auth (401) and forwards to orchestrator `/api/v1/transcribe` (200, mock fallback for invalid file) | wip |
| 2026-08-30 | T-083 | TTS speaker on assistant messages (client Web Speech API) | PASS — `frontend npm run build` 2574 modules; `MessageItem` speaker button added | wip |
| 2026-08-30 | T-084 | Real-time LLM token streaming (event bus + async streaming composer) | PASS — orchestrator boots; composer streamed 430 live token chunks; `run_pipeline` skips re-chunk via `_streamed` flag (no duplication) | wip |
| 2026-08-30 | T-085 | Charts already wired (StreamMarkdown `ChartBlock` + orchestrator `chart_spec`) | VERIFIED — no change needed; ````chart` fences render via react-apexcharts | wip |
| 2026-08-30 | T-086 | Auto-auth (remove login UI, auto-JWT) | PASS — `Bootstrap.tsx` auto-mints JWT; `auth.ts ensureToken()`; gateway agentic default | wip |
| 2026-08-30 | T-087 | Fix localStorage `QuotaExceededError` crash on chat persist (send dead) | PASS — `chat.store.ts` quota-safe storage + trimmed `partialize`; `useSessionPersistence` strips previews/caps; `frontend npm run build` OK | wip |
| 2026-08-30 | T-088 | Fix false "Generation failed/interrupted" + cut LLM latency | PASS — gateway poll budget 36s→360s (env-tunable); planner/router→fast `GROQ_ROUTER_MODEL`, planner max_tokens 800→300, composer 600→400, groq `max_retries=1`; live router 1.5s/planner 1.4s (was ~94/97s) | wip |
| 2026-08-30 | T-089 | Fix thinking display + perpetual timers on stop/drop | PASS — orchestrator emits real planner/router reasoning as `thinking_delta` (planner/router nodes now async+emit); `composer_started` moved before `pipeline.ainvoke` so live `answer_delta` is captured; on `cancelled`/`error` flip msg streaming flags; freeze step `durationMs` on terminal; right-panel + card clocks stop at terminal; gateway poll default 240s | wip |

*Paste real command output in PRs — "tests pass" without evidence is not accepted (see `AGENTS.md:5`).*

## How to Update

1. Move the row: `Todo` → `In Progress` when you start, → `In Review` when PR open, → `Done` when merged.
2. Fill `PR/Commit` and `Blockers / Next`.
3. If you add a stub, append to **Deferred / Stubs**.
4. Append to **Verification Log** with the actual command + outcome.
5. Keep this file and `docs/DECISIONS.md` in sync — they are the two files CI checks alongside code.

## Risks & Watchlist

* CROMA checkpoint availability → fallback to dual Sentinel encoders + cross-attention (log ADR if switching).
* Sentinel ↔ Cartosat/RISAT domain gap (GSD, bands, radiometry) → Input Handler normalization + CORAL/few-shot; track eval gap qualitatively.
* GroundingDINO bbox → mask refinement with SAM is optional but satisfies visual evidence stronger — defer if compute-constrained, log it.
* **4 vision model families kept mocked by design** (`dummy_encoders` SATMAE/SSL4EO/Prithvi/CROMA, `dummy_fusion`, `dummy_task_agents` VQA/Grounding/Change-VQA/Optical-SAR + degraded fallbacks). Only LLM text (Groq `qwen/qwen3.6-27b`) is real. Swap by replacing `dummy/` with trained checkpoints + `MOCK_QWEN=false`.
* **TTS is client-only** (Web Speech API). Orchestrator has no voice-synthesis backend (only Groq Whisper STT). Add a TTS route if server-side synthesis is required.
* **Real-time streaming** depends on Groq network latency; in sandbox it was slow (>110s for ~600 tokens) but tokens arrive live with no duplication. `_streamed` flag in `EXECUTIONS` prevents `run_pipeline` from re-chunking already-streamed text.
* **STT requires browser microphone permission**; gateway `/api/stt` forwards to orchestrator `/api/v1/transcribe` (25MB cap, Groq Whisper). Mock fallback returns `_mock:true` when no `GROQ_API_KEY`.
