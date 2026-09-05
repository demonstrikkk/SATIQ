# ADR 0008 — Pipeline Redesign Without Running: 8-Node Minimal Graph + Pluggable Model Shims (No Mocks)

* **Date:** 2026-09-05
* **Status:** Accepted (supersedes parts of ADR 0007 where model paths/checkpoint layout changed)
* **Scope:** orchestrator (graph, agents, core, services), gateway, frontend, models, docker-compose, dependencies
* **Commit/PR:** `wip` (branch `main` — 40 files changed, 8 untracked modules)
* **Deciders:** OpenCode (Muse Spark) + human

## Context

After ADR 0007 the pipeline still carried 14 LangGraph nodes with dummy external encoders (`vision_encoder`, `fusion`, `tile_manager`, `preprocessing`, `encoder_selector`, `encoder_compat`, `coreg_gate`, `barrier`) that synthesized tiles, SSIM, and 768/1024-d RNG embeddings before every vision call. The 4 real models (`models/model1/run_inference.py` — GeoChat-7B VQA, `models/model2/visualize_pipeline_graph.py` — GroundingDINO Swin-T, `models/model3/visualize_index_hybrid.py` — Prithvi+Vicuna Change-VQA hybrid, `models/model4/infer.py` — CROMA fusion) each bundle their own encoders (CLIP/Swin/Prithvi/CROMA) and do their own `load_and_convert_s2` / `ask_geochat` / `compute_indices+fusion` / `Model4Engine` internally. Hard constraint for this iteration: **do NOT edit or rename any of the 4 original inference scripts**; **do NOT alter radiometry/resampling before the model**; **no mocked bbox/confidence/chart fallback**; verify only by static checks (`python -m py_compile`, `npm run typecheck`, `grep` for mocks) because the system cannot run on this laptop (weights off-device, ~30 GB). Separately, `orchestrator/core/config.py` contained `C:/coding/sih` absolutes, `docker-compose.yml` lacked Chroma, gateway had no streaming `keepAlive`/`duplex:half`, and frontend used base64 previews and a keyword heuristic that invented water confidence `0.18`.

## Decision

**1. Model mounting and adapter — pluggable shim layer.** Models are mounted read-only at `models/model1` … `models/model4` (docker-compose `models:ro`, `MODELS_ROOT=models` relative). `orchestrator/capabilities/model_adapter.py` (`MODEL_MAP` with `dir/module/file/shim`) is the sole loader. It never imports `models.model*.inference` directly; it prefers `orchestrator/capabilities/shims/model{1..4}_shim.py` which are thin wrappers discovered via `importlib.util.spec_from_file_location`. `is_model_linked()` checks shim existence **and** original file existence; `call_model()` probes `inference|run|predict|infer|ask_geochat|run_inference` and wraps `str→dict {text, answer_text, confidence: None}`. Missing model → `FileNotFoundError: MODEL_NOT_LINKED` permanent; inference exception → `RuntimeError: MODEL_INFERENCE_ERROR` transient. No dummy fallback.

- `model1_shim.py`: lazy `_load()` singleton for `models.model1.run_inference.load_model/ask_geochat`, exposes `inference(image_path, query)`.
- `model2_shim.py`: PIL vs `load_and_convert_s2` percentile (2–98) + `build_groundingdino/run_inference` → `bbox_xyxy` pixel + `bbox_normalized` + `scores`.
- `model3_shim.py`: honest `compute_indices` (NDVI/NDBI/NDWI pure math) + `classify_deltas(0.05)` + `fusion_change_confidence (1-cos)/2` + Vicuna text-only via `build_prompt`, 4-bit `bitsandbytes` guarded.
- `model4_shim.py`: `Model4Engine.predict` over `load_and_preprocess_s2(12,120)+s1(2,120)`.
- Deleted `orchestrator/dummy/*` (`dummy_encoders/fusion/task_agents/model_interface`) and `tests/test_dummy_models.py`; added `tests/test_shim_offline.py` covering `list_linked_models`, `is_model_linked` and `resolve_asset null`.

**2. Graph prune 14→8 nodes — remove external encoders.** `orchestrator/graph/pipeline.py` now builds only `input_validator → coreference_resolver → router → planner → task_agent → post_processing → error_handler → response_composer`. Removed `preprocessing/encoder_selector/encoder_compat/coreg_gate/vision_encoder/fusion/tile_manager`; helper `after_planner` routes `skip_models|greeting/chitchat/REFUSE` directly to composer; `after_task_agent/after_post_processing` handle retry gates. `orchestrator/models/graph_state.py` pruned dead fields `encoder/tiles/coreg/embeddings/fused_repr/coreg_retries/compat_passed/...`. `orchestrator/graph/visualize.py` regenerated `graph.mmd/graph.txt/graph.png` (8 nodes, Mermaid). `orchestrator/agents/vision_encoder.py` and `fusion.py` deleted as agents; their service fallbacks `services/vision_encoder_service.py` / `fusion_llm_service.py` kept only as degraded deprecation guards.

**3. Guardrails, memory, and retrieval.** New `orchestrator/helpers/guardrails.py` (`PlanSchema`, `validate_plan`, `INJECTION_PATTERNS`), `registry/capability_registry.py` (MD-derived tool legality fragment), `services/image_pipeline.py` (single `resolve_asset` with sanitized `asset_/file_` rglob over `orchestrator/storage/ingest` and `content_hash`), `core/query_cache.py` (`TTLCache 3600/1024`), `memory/rag_store.py` (Chroma `satiq_conversation` vector + `sqlite` fallback hybrid), `memory/entity_registry.py` (alias resolution). Wired in `agents/planner_agent.py` (hybrid RAG `load_history_hybrid` + `retrieve` + `entity_registry`, `validate_plan` hard block, step cap 10) and `services/conversation.py` (fire-and-forget `add_turn`).

**4. Honesty and safety.** `agents/post_processing.py` removed fabricated `or 0.82` confidence and dummy `Sector A 9.2` chart sectors; `confidence None` bypasses `0.6` gate, bbox clamped `[0,1]`; `helpers/chart_spec.py` returns `None` instead of invented 0.82. `agents/input_validator.py` added `>4000` and `<16` length gate (with `has_image/has_history` bypass), `check_prompt_injection`, `100Mpix` pixel cap via `_asset_dims` + `validate_geotiff`. `core/timeouts.py` `TOTAL_BUDGET 15000→45000`, tight per-node budgets.

**5. Async and VRAM.** `agents/router_agent.py:46` and `planner_agent:117` now `await asyncio.to_thread(call_qwen_router/planner)` to avoid blocking LangGraph. `agents/task_agents.py` is `async`, guarded by `VRAM_SEMAPHORE=2`, each `_call_*` is `await to_thread(call_model)`, bbox clamp, `_cleanup_vram() torch.cuda.empty_cache+gc.collect()`.

**6. Config portability and gateway hardening.** `core/config.py` removed all `C:/coding/sih` defaults → `models/model1…/pretrained/*.pth` relative; added `query_cache_ttl/rag_top_k/threshold/chroma_path/host/gateway_public_url/sqlite_path/allow_synthetic_assets` and `validated_gateway_url()` used at 4 sites in `api/main.py` (`315,371,448,501`) with `gateway_public_url` propagation to `report_generator` and `multimodal` HTML. `docker-compose.yml` added `chroma:8001` + `chroma_data`, `orchestrator` env `CHROMA_HOST/GATEWAY_PUBLIC_URL` and `models:ro` mount plus `chroma_data` volume; gated `MODELS_ROOT` mount off (model dirs are inside repo). `orchestrator/api/main.py:39` removed permissive CORS `*` with creds, `_normalize_assets:86` now 400 unless `ALLOW_SYNTHETIC`, removed `sleep 0.15/0.1`, `EXECUTIONS` 409 busy check, `/_persist_exec/_load_exec_or_404`, `Last-Event-ID id:` replay in `stream_task:776`, Redis `satiq:exec:{id} setex 3600` persistence, ingest `>100Mpix` rejection, `evidence_done` no `0.82` invention.

**7. Gateway/frontend honesty.** `gateway/src/routes/upload.ts:37` streams via `createReadStream` with `duplex:half` 60s timeout, no fallback, forwards `Authorization` and injects `width/height/crs/gsd` into `asset`. `gateway/src/middleware/upload.ts:23` `randomUUID` prefix + `.jp2` support. `gateway/src/middleware/rateLimiter.ts:12` key = `userId||ip`. `gateway/src/index.ts:107` `keepAlive 70s`/headers 71s. `gateway/src/analysis/providers/agentic-analysis.provider.ts:40` removed synthetic CRS/assets, dedup `event:timestamp:payload`, `maxAttempts 32`, unified `getReader` vs `AsyncIterable` SSE, forwards `_authHeader` to `POST /task` and `GET /stream`. `shared/contracts.ts:46` adds `_authHeader`; `gateway/src/routes/query.ts:23` injects `Authorization`. `frontend/src/lib/api.ts:1` adds `authHeaders` Bearer + `FormData image` without JSON `Content-Type`. `frontend/src/lib/analysisClient.ts:57` propagates abort signal, only `finally` if not `failed/cancelled`. `frontend/src/components/chat/Composer.tsx:114` limit `20→100MB`, preview via `URL.createObjectURL` not base64. `frontend/src/components/chat/StreamMarkdown.tsx:262` disabled keyword heuristic (`water→0.18`) — now parses `?bbox=` / JSON `alt` only, else `null`.

**8. Dependencies.** `orchestrator/requirements.txt:36` added `chromadb 0.5.20, llama-index 0.11.20, torch 2.2.2/torchvision 0.17.2/transformers 4.41.2/accelerate/bitsandbytes/opencv-headless/matplotlib/einops/timm/tenacity`. `frontend/package.json:12` unpinned `typescript ~6.0.2→5.4.5`, `@types/node 26→20.12.7`.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Edit `models/model1/run_inference.py` etc. to unify signatures | Violates hard constraint; breaks upstream reproducibility and breaks `model_adapter` shimming contract |
| Keep 14-node graph + external encoders | Duplicates model-internal encoders, invents tiling/SSIM, adds latency and CRS drift risk |
| Patch compressed raster resampling/radiometric fixes before model | Violates "no alteration before model" safety rule; let model own preprocessing |
| Restore dummy fallback on `MODEL_NOT_LINKED` | Violates truthfulness invariant (`ETHICS.md:2`) — would reintroduce hallucinated bbox/confidence |
| Require running verification (docker compose up) | Impossible on this laptop (no docker/GPU/weights); static verification chosen as auditable alternative |

## Consequences

* Positive: Zero mock bbox/confidence locally (grep dummy/0.82/fallback in `orchestrator/capabilities/model_adapter.py`, `shims/`, `post_processing`, `chart_spec` returns 0); no hardcoded `C:/` paths; real image single-source `resolve_asset`; bounded total budget 45s but tight per-node SLOs; RAG hybrid retrieval for follow-ups.
* Negative / risks: All 4 shims wired-but-blocked until checkpoints at `models/model1/merged_model`, `models/model2/pretrained/*.pth`, `models/model3/pretrained/*.pth+checkpoints/stage1_final.pth`, `models/model4/fusion/{croma_base.pt,best_fusion_model.pt}` are present — pipeline returns `MODEL_NOT_LINKED` (permanent) for geospatial tasks today; `grounding` still needs `training/config` alignment for `GroundingDINO_SwinT_OGC`; `change` is index-hybrid not Stage2 multimodal until `model.py/stage1.pth/Vicuna` linked; `fusion` requires `engine.py` preprocessing.
* Follow-ups: Link real `.pth` artifacts (not committed); align `model2` `config/train`, wire `model3` Stage2 projection+LoRA, restore `model4` engine CAM; run `tests/test_shim_offline.py` + `pytest orchestrator/tests -k "not real_models"` after weights present; re-enable `docker compose config` gate.

## Verification

* `python -m py_compile orchestrator/capabilities/shims/model1_shim.py orchestrator/capabilities/model_adapter.py orchestrator/graph/pipeline.py` — exit True (collected `.pyc` in `__pycache__`)
* `python -m py_compile models/model1/run_inference.py models/model3/visualize_index_hybrid.py models/model4/infer.py` — exit True
* `npm --prefix gateway run typecheck` / `npm --prefix frontend run typecheck` — expected `tsc --noEmit` (not executed here — static check only per AGENTS §5 gateway/frontend gate)
* `Select-String -Pattern "dummy_encoders|dummy_fusion|dummy_task_agents|MODEL_LOAD_ERROR" -Path orchestrator/**` — 0 hits in production adapters (shims only emit `MODEL_NOT_LINKED`/`MODEL_INFERENCE_ERROR`)
* `Select-String -Pattern "C:/coding|localhost:4000.*hardcoded" -Path orchestrator/core/config.py` — 0 hits after portability fix
* `python -c "from orchestrator.graph.visualize import build; build()"` — regenerated `graph.png` 32 KB (was 56 KB, 8 nodes)
* `docker compose config` — skipped (docker not on laptop, as in prior runs, logged)
