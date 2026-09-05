# Friend Handoff — 6 Gaps to Production (Copy-Paste Prompts)

> Your friend has 6 well-scoped tasks. Give them this file. They run `scripts/preflight.ps1` before/after each task, and keep `docs/DECISIONS.md` + `docs/PROGRESS.md` updated (AGENTS.md §8).

## Repo Snapshot (what you have)
- **Pruned:** 14→8 node LangGraph `graph/pipeline.py:1`, `MAX_REFLECTION_ITERATIONS=2`, `TOTAL_BUDGET 45000`
- **Single-GPU:** `VRAM_SEMAPHORE(2)` + `asyncio.to_thread` in `task_agents.py:14`, no Groq, Ollama `qwen3.5:9b` only
- **4 shims:** `capabilities/shims/model{1..4}_shim.py` wrapping `models/model1/run_inference.py` etc. (DO NOT EDIT originals)
- **4-tier memory:** `memory/rag_store.py` dual Chroma (`satiq_conversation` 90d + `satiq_semantic` 180d), `memory/memory_orchestrator.py` hybrid 0.7/0.3+decay, `services/conversation.py` consolidation, `entity_registry`, `/api/v1/memory`
- **Ingest fixed:** `.tif/.tiff/.geotiff/.gtiff/.jp2` allowlist, `gateway/store/assetStore` enrichment, `image_pipeline resolve_asset` fallback, `Composer pendingUploads` 15s guard
- **Verify without GPU:** `python -m py_compile` + `pytest tests/e2e/test_replay.py` (7 passed) + `powershell -File scripts/preflight.ps1`

---

## Master Prompt — Paste at Top of Every Codex/Cursor Session

```
You are editing Satiq at C:\path\to\Satiq on Windows (friend's machine).

Hard invariants (never break):
- DO NOT edit models/model1/run_inference.py, models/model2/visualize_pipeline_graph.py, models/model3/visualize_index_hybrid.py, models/model4/infer.py — shim only (orchestrator/capabilities/shims/model{1..4}_shim.py)
- 8-node DAG MAX_REFLECTION_ITERATIONS=2, 45s TOTAL_BUDGET, input_validator 100Mpix + CRS hard gate (EPSG:), allow_synthetic_assets=false prod
- Ollama qwen3.5:9b only (LLM_PROVIDER=local). No Groq/Mistral. Confidence None = honest pass (post_processing)
- Scope memory/tenant by session_id; DELETE propagates to Chroma both + SQLite + disk
- Every code change touches docs/DECISIONS.md + docs/PROGRESS.md (and ADR if behavior/data/dep)

Verify before/after each gap:
  python -m py_compile orchestrator/memory/*.py orchestrator/services/*.py orchestrator/agents/*.py orchestrator/api/main.py
  powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1
  C:\path\to\.venv\Scripts\python -m pytest tests/e2e/test_replay.py -v  # must stay 7 passed
  npm --prefix gateway run typecheck  # if gateway touched
```

---

### GAP 1 — Quantitative Evaluation & Benchmark Harness
**Current:** `tests/e2e/test_replay.py` only tests `input_validator` rejections; no mIoU/F1/accuracy.

**Copy-paste prompt:**
```
Task GAP-1: Build tests/benchmarks/eval_suite.py + fixtures.

- Create tests/benchmarks/ with 20 reference samples (tiny synthetic GeoTIFFs 64x64 via rasterio + script) covering vqa/grounding/change_vqa/fusion. Ground truth: bbox [x1,y1,x2,y2] normalized, change class, answer keyword.
- Implement eval_suite.py: for each sample call image_pipeline.resolve_asset + model_adapter.call_model (expect MODEL_NOT_LINKED in CI — mock with shim stub that returns dummy bbox/answer when env MOCK_EVAL=1), compute grounding mIoU (intersection/union), change F1 (precision/recall on change class), VQA accuracy (keyword match), output Markdown + JSON to tests/benchmarks/report.{md,json} with p50 latency from EXECUTIONS metrics.
- Add make target `make eval` -> `MOCK_EVAL=1 pytest tests/benchmarks/eval_suite.py -v` and CI gate `benchmarks/report.md` artifact.
- Verify: MOCK_EVAL=1 .venv\Scripts\python tests/benchmarks/eval_suite.py generates report with mIoU/F1/accuracy rows, py_compile 0, replay 7 still pass. Log in docs/DECISIONS.md + docs/PROGRESS.md T-096.

Do not add new deps beyond rasterio/numpy already in requirements; keep weights mocked via MOCK_EVAL.
```

### GAP 2 — Automated Model Weight Provisioning
**Current:** `scripts/preflight.ps1` warns `MODEL_NOT_LINKED` but no downloader.

**Copy-paste prompt:**
```
Task GAP-2: Build scripts/download_weights.py (single command).

- Use huggingface_hub snapshot_download + hf_transfer if available, else curl fallback. Map:
  model1 GeoChat-7B -> liuhaotian/geochat-7b -> models/model1/merged_model
  model2 GroundingDINO Swin-T OGC -> IDEA-Research/grounding-dino-base -> models/model2/pretrained
  model3 Prithvi ViT -> ibm-nasa-geospatial/Prithvi-100M -> models/model3/pretrained + stage1_final.pth (local)
  model4 CROMA -> MSCROMA/CROMA -> models/model4/fusion/croma_base.pt
- Script args: --model all|1|2|3|4 --check (verify sha), --dry-run (list URLs). Respects HF_TOKEN env, shows progress, verifies file exists then prints is_model_linked status via model_adapter.list_linked_models().
- Add README section `## Weights (one-command)` and Makefile `make weights` -> `python scripts/download_weights.py --model all`.
- Verify: python -m py_compile scripts/download_weights.py 0, python scripts/download_weights.py --dry-run lists 4 URLs, preflight MODEL_NOT_LINKED warnings clear after download. Log decisions.

Do not commit weights; .gitignore models/model*/*.pt,*.pth,*.safetensors (keep README.md).
```

### GAP 3 — VRAM Queue Depth & Bounded Rejection (HTTP 503)
**Current:** `VRAM_SEMAPHORE(2)` limits to 2 concurrent, but 10 queued queries sit until 45s Gateway timeout.

**Copy-paste prompt:**
```
Task GAP-3: Bounded VRAM queue with 503 + SSE queue_position.

- In orchestrator/agents/task_agents.py add _VRAM_QUEUE counter (asyncio.Lock + int) incremented before semaphore acquire, decremented after. If counter > 4 (config via env VRAM_MAX_QUEUE=4) raise HTTPException 503 via task_agent_node -> state error_code=queue_full error_type=permanent, with payload {queue_position, estimated_wait_ms: queue*6000}.
- In orchestrator/api/main.py add pre-check before pipeline: if _VRAM_QUEUE > limit return 503 JSON {error: queue_full} + header Retry-After. Also add SSE event `queue_position` in agentic-analysis.provider polling fallback so frontend can show spinner position.
- Frontend: frontend/src/lib/analysisClient.ts handle 503 -> applyExecutionEvent error with code queue_full, UI shows "GPU busy — retry in Xs" + auto-retry button (once).
- Config: orchestrator/core/config.py add vram_max_queue: int Field(default=4, alias=VRAM_MAX_QUEUE).
- Verify: spam 6 concurrent POST /api/v1/task with same image -> 2 run, 4 queued, 7th returns 503, SSE queue_position emitted, replay 7 still pass, py_compile 0. Log.
```

### GAP 4 — Automatic CRS Reprojection & Extent Clipping
**Current:** `input_validator` rejects CRS mismatch/out-of-extent; user must pre-process.

**Copy-paste prompt:**
```
Task GAP-4: Add reprojection helper in orchestrator/services/tiling.py (reuse existing file).

- Implement reproject_to_target(src_path: Path, dst_crs: str = "EPSG:4326", clip_bbox: tuple | None = None) -> Path using rasterio.warp.reproject + calculate_default_transform, with WarpedVRT. Handles UTM zone heterogenous inputs (e.g., EPSG:32643 vs 32644) -> EPSG:4326 before shim. Preserve dtype/bands/nodata, write to /tmp/reproj_{stem}_{dst_epsg}.tif, return Path.
- Wire in image_pipeline.resolve_asset or task_agents before call_model: if asset.crs != target crs, call reproject_to_target and pass reprojected path to shim (original preserved). Do not alter radiometry beyond warp (no stretch).
- Add extent clipping: if query bbox out-of-extent, clip to raster bounds and log error_log "bbox clipped {orig}->{clipped}" (vs reject).
- Verify: craft two rasters EPSG:32643 + EPSG:32644, query with AOI in 4326 -> both reprojected, no CRS mismatch 400, shim receives 4326. py_compile 0, replay 7 still pass. Log decisions; mark as non-breaking (fallback to reject if rasterio.warp missing).
```

### GAP 5 — Node-Level Telemetry & Latency Breakdown Endpoint
**Current:** traces in Redis `EXECUTIONS.events` + `node_latencies`, but no aggregated percentiles.

**Copy-paste prompt:**
```
Task GAP-5: Expose GET /api/v1/metrics telemetry.

- Extend orchestrator/core/metrics.py to track per-node histogram (input_validator, router, planner, task_agent, post_processing, response_composer) + VRAM queue depth + peak VRAM (torch.cuda.max_memory_allocated if available). Compute p50/p95/p99 over last 100 executions (sliding window in Redis or in-mem fallback).
- Enhance GET /api/v1/metrics in orchestrator/api/main.py to return {per_node: {p50,p95,p99,avg,count}, vram: {peak_mb, queue_depth, semaphore_permits}, total_budget_ms: 45000, max_reflection: 2}. Add query param ?session_id to scope to one session if given.
- Keep existing /health + /tools untouched. Add Prometheus-style text at /metrics if Accept: text/plain.
- Verify: run 3 mock tasks (MOCK_EVAL), curl /api/v1/metrics returns per-node p50 < planner ~1.5s, task_agent ~2s, gateway tsc 0, py_compile 0, replay 7 still pass. Log.
```

### GAP 6 — Frontend Unlinked Model UI Guidance
**Current:** shims fail-closed `MODEL_NOT_LINKED` but frontend shows generic error.

**Copy-paste prompt:**
```
Task GAP-6: Dedicated MODEL_NOT_LINKED banner in frontend.

- In frontend/src/lib/analysisClient.ts SSE error handler, detect payload.code === "MODEL_NOT_LINKED" or message includes MODEL_NOT_LINKED (from task_agent permanent error). Emit ExecutionEvent with code MODEL_NOT_LINKED (not generic error).
- In frontend/src/components/chat/StreamMarkdown.tsx (or ChatCanvas/ThinkingPanel) catch error code MODEL_NOT_LINKED and render SetupBanner: icon + "Models not linked — run download" with code block `python scripts/download_weights.py --model all` + `docker compose up --build` + link to docs/FRIEND_HANDOFF.md Weights table + preflight status (calls GET /api/v1/metrics to show linked_models). Provide Copy button.
- Do not hide generic errors; only branch on MODEL_NOT_LINKED. Keep existing bbox/chart rendering.
- Verify: trigger mock 503 MODEL_NOT_LINKED (set env MOCK_MODEL_LINKED=0 in shim), frontend shows banner not generic toast, tsc 0, replay 7 still pass. Log.
```

---

## Execution Order & Verification

Run in order: **GAP 2 → GAP 3 → GAP 4 → GAP 1 → GAP 5 → GAP 6** (weights first, then queue/reproj unblock evaluation, then harness/metrics/UI). After each:

```
python -m py_compile orchestrator/** gateway/src/**  # 0
powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1  # py_compile OK, cassette 6
.venv\Scripts\python -m pytest tests/e2e/test_replay.py -v  # 7 passed (must never break)
npm --prefix gateway run typecheck  # if gateway touched
curl http://localhost:8000/health  # ollama_reachable true after weights
```

Commit per GAP with `docs/DECISIONS.md |0000| + docs/PROGRESS.md T-09x` per AGENTS.md §8. Push branch `friend/gaps-1-6` for review.

## What Not to Do
- Do not edit `models/model{1..4}/*.py` originals
- Do not add GraphRAG/Neo4j (deferred per ADR 0009/0010)
- Do not mock bbox/confidence in production path — MOCK_EVAL only in tests
- Do not widen MAX_REFLECTION beyond 2 or TOTAL_BUDGET beyond 45000
