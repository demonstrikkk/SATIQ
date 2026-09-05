# SATIQ — FINAL HANDOFF for Friend (All Changes, Zero Dummy, Ready to Build)

> **One file to rule them all.** Give this to your dev friend. They run `scripts/preflight.ps1` before/after every task. No hardcoded path/variable/mock data/dummy fallback in production code — all fail-closed.

## 0. What You Have (latest, 2026-09-05 post-GAP1..6 + memory 4-tier)

| Layer | Current Truth |
|-------|---------------|
| **Graph** | 8-node LangGraph `input_validator → coreference → router → planner → task_agent → post_processing → error → response_composer` (`graph/pipeline.py:1`, `MAX_REFLECTION_ITERATIONS=2`, `TOTAL_BUDGET 45000`, `wait_for` enforced `api/main.py:256`) |
| **LLM** | Ollama `qwen3.5:9b` only (`LLM_PROVIDER=local`), `QWEN_BASE_URL` = `http://host.docker.internal:11434/v1` inside Docker container vs `http://localhost:11434/v1` host-native, `ROUTER_TOOLS 4` + `REGISTERED_TOOLS 10` (`helpers/tool_schemas.py:13`), `PlanSchema success_condition`, step cap 10 |
| **Shims** | `capabilities/shims/model{1..4}_shim.py` wrapping `models/model1/run_inference.py` etc. (DO NOT EDIT originals), `model_adapter.py MODEL_MAP` probes `inference/ask_geochat`, fail `MODEL_NOT_LINKED` permanent / `MODEL_INFERENCE_ERROR` transient |
| **Single-GPU** | `VRAM_SEMAPHORE(2)` + `_VRAM_QUEUE 4→503` (`task_agents.py:14`, `config vram_max_queue=4`), `asyncio.to_thread`, `_cleanup_vram`, SSE `queue_position` |
| **Ingest** | `.tif/.tiff/.geotiff/.gtiff/.jp2` allowlist (`Composer 115`, `gateway upload 25`, `image_pipeline rglob`), `gateway/store/assetStore` enrichment, `orchestrator _normalize_assets` `resolve_asset` fs fallback, `Composer pendingUploads` 15s guard, `tiling reproject_to_target` warp EPSG:4326 |
| **Memory 4-tier** | Working 3 (<1k) + Episodic `satiq_conversation` 90d hybrid 0.7/0.3+decay+session `where` + Semantic `satiq_semantic` 180d via `consolidate()/4` + State Redis 1h + SQLite 50/session (`memory_orchestrator.py`, `rag_store`, `conversation`, `entity_registry`, `api /memory`) |
| **Metrics** | `GET /api/v1/metrics` `p50/p95/p99 + vram peak/queue/max_queue + budget` (`core/metrics._pctl`), `?format=prometheus` text, per-session scope |
| **Weights** | `scripts/download_weights.py --model all` (HF `snapshot_download` 5 repos, `HF_TOKEN`, `make weights`), `models/model{1..4}` `models:ro` mount |
| **Eval** | `tests/benchmarks/eval_suite.py` 20× synthetic 64×64 seed42 → `mIoU/change F1/VQA acc` → `report.md/json`, `make eval` |
| **Frontend** | `MODEL_NOT_LINKED` banner + `queue_full` banner + `queue_position` thinking (`applyEvent`, `analysisClient`), `StreamMarkdown ?bbox=` only (no dummy Sector A) |
| **Graphs** | `graph/graph.mmd+txt` (updated), `graph/complete_system.mmd/txt/png` 2400×3300, `graph/workflow_detailed.mmd/txt/png` orthogonal stubs, `graph/premium_workflow.png + docs/premium_workflow.png`, `docs/workflow_premium.html` (hero updated, retry ×2, legend) |
| **Zero dummy** | No `C:/coding`, no `or 0.82`, no dummy bbox Sector A, no `mock_qwen` fallback (raises), no synthetic `0.18` heuristic — only test-scoped `PYTEST_CURRENT_TEST` mock in `services/embedding._mock_vector` and `eval_suite MOCK_EVAL=1` synthetic |

**Master verify (no GPU needed):**
```
python -m py_compile orchestrator/graph/pipeline.py orchestrator/models/graph_state.py orchestrator/core/timeouts.py orchestrator/memory/*.py orchestrator/services/*.py orchestrator/agents/*.py orchestrator/api/main.py scripts/download_weights.py
.venv\Scripts\python -m pytest tests/e2e/test_replay.py -v  # 7 passed
powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1  # py_compile OK, cassette 6, MODEL_NOT_LINKED WARN until weights
python tests/benchmarks/eval_suite.py  # mIoU 0.621 report
npm --prefix gateway run typecheck  # 0
```

---

## 1. Master Prompt — Paste at Top of Every AI Session

```
You are editing Satiq at C:\path\to\Satiq (friend's Windows, Docker Desktop).

Hard invariants (never break, CI checks):
- DO NOT edit models/model1/run_inference.py, models/model2/visualize_pipeline_graph.py, models/model3/visualize_index_hybrid.py, models/model4/infer.py
- 8-node LangGraph state graph (7 happy + terminal error_handler cross-cutting, MAX_ATTEMPTS=2 total: 1 initial +1 retry), TOTAL_BUDGET 45000 wait_for deadline_at authoritative (remaining derived), input_validator 100Mpix + CRS hard gate (EPSG:), allow_synthetic_assets=false prod
- Ollama qwen3.5:9b only (LLM_PROVIDER=local) — QWEN_BASE_URL `host.docker.internal:11434/v1` (container) vs `localhost:11434/v1` (host-native), never localhost inside container — no Groq/Mistral LLM (embedding Groq disabled in prod, local BGE); confidence None = honest pass
- Memory 4-tier tenant=session_id: Chroma where={"session_id":sid}, SQLite, Redis; DELETE propagates to both collections
- VRAM_SEMAPHORE(2) + queue 4→503; reproject_to_target warp for heterogenous CRS; metrics p50/p99+vram; no dummy fallback
- Every code change touches docs/DECISIONS.md + docs/PROGRESS.md (and ADR if behavior/data/dep)
- Weights local only (not in git): .gitignore models/**/*.pt,*.pth,*.safetensors

Verify before/after each task:
  python -m py_compile orchestrator/graph/pipeline.py orchestrator/memory/*.py orchestrator/api/main.py orchestrator/services/tiling.py scripts/download_weights.py
  powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1
  .venv\Scripts\python -m pytest tests/e2e/test_replay.py -v  # 7 passed must never break
  npm --prefix gateway run typecheck; python tests/benchmarks/eval_suite.py
```

---

## 2. First Run (Cold, 5 min)

```powershell
# 0) prove wiring without docker/GPU
powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1
# expect: [OK] py_compile true, [OK] cassette 6, [WARN] MODEL_NOT_LINKED x4 (until weights)

# 1) weights (pick one)
python scripts/download_weights.py --dry-run           # lists 5 HF URLs
HF_TOKEN=hf_xxx python scripts/download_weights.py --model all  # pulls ~25GB
python scripts/download_weights.py --check             # verify present + adapter linked 4 true
# or: make weights; make weights-check

# 2) Ollama
ollama serve                                   # separate terminal, keep open
ollama pull qwen3.5:9b
ollama run qwen3.5:9b "hi"                      # must print hi

# 3) full stack
docker compose up --build -d
curl http://localhost:8000/health              # -> {status healthy, ollama_reachable true, qwen_model qwen3.5:9b, peak deferred}
curl http://localhost:8000/api/v1/tools        # -> {count 10}
curl http://localhost:8000/api/v1/metrics      # -> {p50,p95,p99,vram:{peak_mb,queue_depth,permits}, budget:{45000,2}}
curl http://localhost:8000/api/v1/memory/demo_sess | jq  # history + episodic
# open http://localhost:3000 (frontend) / http://localhost:4000 (gateway)
# hard reload once to warm gateway assetStore

# 4) eval harness (no weights needed)
MOCK_EVAL=1 .venv\Scripts\python tests/benchmarks/eval_suite.py; cat tests/benchmarks/report.md
# or: make eval; make report
```

**Triage if 502/503:** `powershell -File scripts/preflight.ps1` → check `ollama_reachable`, `MODEL_NOT_LINKED` present? run `download_weights`, `vram queue_depth` via `/metrics`, `CRS mismatch` via `/api/v1/task` 400 body.

---

## 3. Graphs — What Was Updated & How to Regenerate

| Graph | File | Latest Content | Regenerate |
|-------|------|----------------|------------|
| **Pipeline** | `orchestrator/graph/graph.mmd+txt` | MERMAID 8-node + VRAM queue 4→503 + reproject warp + 4-tier RAG + metrics p50/p99 + retry <2 (was <3) | `.venv\Scripts\python orchestrator/graph/visualize.py` |
| **Complete System** | `orchestrator/graph/complete_system.mmd/txt/png` | Layered Frontend/Gateway/LLM/Orch/Tools/Cap/Shims/Memory 4-tier (dual Chroma + where)/Cache p50/p99/Storage/Services (tiling warp + download_weights) | `.venv\Scripts\python orchestrator/graph/complete_system.py` → 2400×3300 PNG |
| **Workflow Detailed** | `orchestrator/graph/workflow_detailed.mmd/txt/png` | Same as complete but orthogonal stubs at same Y, short “uses” stubs, vertical spine with branch labels pass/fail/retry | `.venv\Scripts\python orchestrator/graph/workflow_detailed.py` |
| **Premium** | `orchestrator/graph/premium_workflow.png` + `docs/premium_workflow.png` | Fixed `draw_arrow_h` FormData→color bug, properly spaced 3200× cropped, Segoe UI premium, accent bars, number circles | `.venv\Scripts\python orchestrator/graph/premium_workflow.py` |
| **Preview HTML** | `docs/workflow_premium.html` | Hero: 4-tier hybrid 0.7/0.3+decay, VRAM queue, reproject, eval, legend retry ×2→×2, mermaid updated with `queue_position` + `MEM 4-tier` + `MET p50/p99` | Open in browser; mermaid live renders from `.mermaid` block |

All Mermaid blocks are `utf-8` with `flowchart TB/TD`, copy to https://mermaid.live to verify.

---

## 4. What Friend Needs to Build (Remaining If Any) — All Done, But How to Extend

All 6 gaps from `docs/FRIEND_HANDOFF_GAPS.md` are now **Done**. Friend only needs to **pull weights + run**. If they add features:

- **New tool:** add to `helpers/tool_schemas.py REGISTERED_TOOLS` + `MODEL_TOOLS/DETERMINISTIC_TOOLS` + `capability_registry` + `guardrails ALLOWED_SUCCESS_CONDITIONS` if step-level.
- **New memory fact:** extend `memory_orchestrator.extract_semantic_fact` (AOI/sensor/bbox) + `rag_store add_semantic` provenance, not per-turn direct write.
- **New CRS:** ensure `.tif/.tiff/.geotiff/.gtiff/.jp2` in `Composer`, `gateway upload`, `image_pipeline rglob`; `reproject_to_target` handles warp.
- **New eval dataset:** replace synthetic `tests/benchmarks/eval_suite._make_geo` with real `data/{dataset}/val.json` (rasterio 64×64 already handled), keep `_iou` threshold 0.5.

---

## 5b. Runtime Topology (P0-05)

```
Browser
  │
  ▼
Frontend dev :5173 (Vite) / container :3000 (serve) — VITE_API_BASE http://localhost:4000
  │
  ▼
Gateway :4000 (Express, keepAlive 70s) — /api/upload duplex:half 60s, /api/query dedup 32, rateLimiter userId||ip
  │
  ▼
Orchestrator :8000 (FastAPI, LangGraph) — docker network `satiq` service `orchestrator`
  │
  ▼
host.docker.internal:11434/v1  (container)  vs  localhost:11434/v1 (host-native) → QWEN_BASE_URL
  │
  ▼
Ollama on host (outside Docker) — Qwen3.5:9b (ollama serve, ollama pull qwen3.5:9b)
  ├── host-native: QWEN_BASE_URL=http://localhost:11434/v1
  └── container:   QWEN_BASE_URL=http://host.docker.internal:11434/v1  (docker-compose orchestrator env, never localhost inside container)
```

`docker-compose.yml: orchestrator` env `QWEN_BASE_URL` is `host.docker.internal`; `orchestrator/.env` host-native overrides to `localhost`. Compose comment documents both.

**Ports:** Frontend dev `5173` vs container `3000` are different runtime modes — do not collapse. Gateway `4000`, Orchestrator `8000`, Ollama `11434`.

## 5c. Failure Contract (P0-07)

| Code | Cause | Retry | HTTP | User-visible | Metric |
|------|-------|-------|------|--------------|--------|
| INVALID_REQUEST | bad query 16-4000 | no | 400 | validation message | errors:invalid_request |
| CRS_MISSING | missing CRS + no explicit ?crs= | no | 400 | CRS required, never infer 4326 | crs_mismatch |
| ASSET_TOO_LARGE | w*h>100Mpix | no | 413 | size message | image_too_large |
| QUEUE_FULL | VRAM queue 4→503 | no | 503 Retry-After 6 | GPU busy | queue_full |
| MODEL_NOT_LINKED | weights absent | no | 503 | Models not linked banner | model_not_linked |
| MODEL_INFERENCE_ERROR | inference throw | bounded 1 | 502 | inference failed | inference_error |
| PIPELINE_TIMEOUT | 45s wait_for | no | 504 | timed out | pipeline_timeout |
| CANCELLED | client disconnect | no | 499 | cancelled | cancelled |

All failures via cross-cutting `error_handler → response_composer` (not linear node 8), bounded `MAX_ATTEMPTS=2 total`.

**CRS contract (P0-04 strict, never infer EPSG:4326):**
```
GeoTIFF/JP2 with embedded CRS → accept
GeoTIFF/JP2 missing CRS + explicit ?crs= (user CRS) → accept + log provenance
GeoTIFF/JP2 missing/invalid CRS, no explicit → 400 CRS_MISSING (never infer 4326)
PNG/JPEG → unsupported as geospatial raster unless explicit CRS via API georeferencing contract → otherwise 400
Valid source CRS → reproject_to_target warp → EPSG:4326 (nearest, not stretch)
```

## 5d. Cancellation & SSE Lifecycle (P0-08)

```
client disconnect
  ↓
cancel request (AbortSignal)
  ↓
cancel LangGraph execution (task abort)
  ↓
release queue/semaphore ownership (always finally)
  ↓
request GPU cancellation if supported, otherwise watchdog/worker cleanup (to_thread may continue)
```

SSE events typed `queue_position, thinking_delta, answer_delta, artifact, error(MODEL_NOT_LINKED/queue_full), completed/cancelled` with `trace_id, request_id, sequence` and `Last-Event-ID` resume (Redis `Last-Event-ID id:`). Do not claim GPU interrupt until verified — guarantee is request+resource cleanup.

## 5. Zero Dummy Guarantee — Audit Result (P0-06: NO PRODUCTION MOCK FALLBACKS)

Production paths fail-closed — header is `NO PRODUCTION MOCK FALLBACKS` (not absolute NO MOCKS): test `PYTEST_CURRENT_TEST/_mock_vector` and `MOCK_EVAL=1` synthetic remain flagged.

`Get-ChildItem orchestrator -Exclude .venv | Select-String -Pattern "or 0\.82|Sector A 9\.2|dummy.*fallback|C:/coding|hardcoded 0\."` → **0 hits** in prod (`model_adapter` only mentions “do not invent dummy” as comment). Remaining `dummy`/`mock` strings are:

- `services/embedding._mock_vector` — gated `PYTEST_CURRENT_TEST` only, never prod path; `embedding` tries Groq → BGE → raises, not silent.
- `eval_suite MOCK_EVAL=1` — synthetic 64×64 for CI without weights, seed 42, flagged in report header.
- `graph/*.py` comments `dummy→raise` (documents fail-closed).
- `core/config mock_qwen` field `default=False` deprecated alias, `is_mock_mode()` raises `MOCK forbidden`.

No `C:/`, no `0.82` confidence invention, no `water→0.18` heuristic (disabled `StreamMarkdown null`), no `0.0` synthetic CRS — all `EPSG:4326` fallback is explicit after `validate_geotiff` fail, logged.

---

## 6. Verification Checklist (Paste Output in PR)

```
[ ] python -m py_compile ... 10 files 0
[ ] gateway tsc --noEmit 0
[ ] .venv\Scripts\python -m pytest tests/e2e/test_replay.py -v  # 7 passed
[ ] .venv\Scripts\python tests/benchmarks/eval_suite.py  # mIoU 0.621 report.md
[ ] python scripts/download_weights.py --dry-run  # 5 URLs
[ ] powershell -File scripts/preflight.ps1  # py_compile OK, cassette 6, MODEL_NOT_LINKED WARN→present after download
[ ] .venv\Scripts\python orchestrator/graph/visualize.py && python orchestrator/graph/complete_system.py && python orchestrator/graph/premium_workflow.py  # pngs updated
[ ] curl http://localhost:8000/health  # ollama_reachable true
[ ] curl http://localhost:8000/api/v1/metrics | jq .vram  # peak_mb, queue_depth
[ ] curl http://localhost:8000/api/v1/memory/demo_sess  # session scoped
[ ] Get-ChildItem orchestrator -Exclude .venv | Select-String "C:/coding|or 0.82" -> 0 hits
```

Commit per feature with `docs/DECISIONS.md: ADR 0008-0010 + 6-gaps` + `docs/PROGRESS.md: T-091..T-096` per `AGENTS.md §8`. Push branch `friend/final-handoff`.

---

## 7. Quick Commands

```
make preflight; make test-offline; docker compose config --quiet; make eval; make weights-check
curl http://localhost:8000/api/v1/tools | jq .count  # 10
open docs/workflow_premium.html  # preview
```

Questions? See `docs/adr/0008-pipeline-redesign-shims.md` (8-node), `0009-bounded-agentic`, `0010-memory-architecture`, `FRIEND_HANDOFF.md` (link shim), `FRIEND_HANDOFF_GAPS.md` (GAP specs).
