# ADR 0007 — Replace Dummy/Mock Models with Real Fine-Tuned Models

* **Date:** 2026-08-31
* **Status:** Accepted
* **Scope:** orchestrator/capabilities, orchestrator/agents/task_agents, orchestrator/models/analysis_result, orchestrator/core/config, orchestrator/tools
* **Commit/PR:** wip (Task Prompt: Replace Dummy/Mock Models with Real Fine-Tuned Models)
* **Deciders:** OpenCode (Muse Spark) + human

## Context

Pipeline has run on `dummy_encoders` (SatMAE/SSL4EO/Prithvi/CROMA RNG) + `dummy_task_agents` (static 0.78-0.90 confidence, fake bbox) + mocked Qwen 3.5 9B heuristic for 6 milestones. Task Prompt requires swapping the 4 dummy capability tools for real fine-tuned models and 2 standalone inference scripts without breaking the LangGraph contract, without faking spatial evidence, and without silent mock fallback. Checkpoints do not yet exist on this laptop (only `.gitkeep` in `capabilities/*`), so the wiring must be honest: missing weights → `MODEL_LOAD_ERROR`, not dummy text. CRS/GSD hard gate must stay first. Confidence must be real or `null` per rule 7.

## Decision

Wire 4 real capabilities behind `orchestrator/capabilities/model_manager.py` singleton (thread-safe, load-once, `manager.get(name, loader)`), extend `core/config.py` with checkpoint paths (`PRETRAINED_DIR`, `GDINO_CONFIG/WEIGHTS`, `VQA_WEIGHTS`, `CROMA_WEIGHTS`, `CHANGE_STAGE1_CKPT`, `VICUNA_WEIGHTS`, `IMAGE_SIZE`, `S2_PERCENTILE_*`), and replace `agents/task_agents.py` dummy calls with file-location-loaded real tool calls (`capabilities/single_image/vqa.py`, `grounding.py` with S2 percentile stretch verbatim, `temporal/change_vqa.py` stage1_index_hybrid honest + NDVI/NDBI/NDWI + fusion cosine, `fusion/optical_sar.py` CROMA). Add `orchestrator/tools/visualisation_tool.py` adapter (`@tool generate_visual_evidence`) that delegates to real `visualisation.py` if present else fallback artifact dict. Extend `models/analysis_result.py` additively: `confidence: Optional[float]` (null if not available), `artifacts`, `metadata`, `pipeline_mode` on all 5 schemas. Keep `graph/pipeline.py` routing unchanged (conditional edges, retry counts), only `task_agent_node` maps tool contract `§5` to `GraphState` (`success` → `task_output`, `error` → `error_type permanent/transient` for `error_handler` retry `max_transient 2`). `agents/vision_encoder.py` / `agents/fusion.py` remain as shared fallback (documented, not removed) because capabilities now own their encoders — no duplicated reload.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Keep dummy fallback silently in production | Violates hard rule 1 & 4 — fabricates bbox/confidence, hides missing checkpoint |
| Rewrite pipeline graph / retry thresholds | Unnecessary; real outputs already fit existing `GraphState` via additive fields, retries already handle `MODEL_INFERENCE_ERROR` |
| Reload weights per-request | Violates rule 5, GPU OOM + latency; manager cache required |
| Break `AnalysisResult` schema (remove/add required fields) | Breaks frontend `response_composer_node` + `add_trace`; additive `Optional` preserves consumers |
| Direct `import capabilities.*` in task_agents | Fails under pytest without `PYTHONPATH`; use `importlib.util.spec_from_file_location` with `REPO_ROOT` for robustness, plus top-level `capabilities/__init__.py` |

## Consequences

* Positive: No hardcoded `0.8` remains in real tools (grep verified); bbox/scores come from GDINO `scores` tensor or N/A; change categories from real `classify_deltas`; fusion confidence from CROMA `per_modality_confidence` or null; `MODEL_LOAD_ERROR` is explicit and testable.
* Negative / risks: All 4 capabilities currently wired-but-blocked on missing checkpoints (`capabilities/*/weights/` empty) — pipeline tests now expect `MODEL_LOAD_ERROR` not success for change/fusion with dummy ids; real checkpoints must be dropped in per `capabilities/*/weights/` documented paths. `rasterio/torch/groundingdino/transformers` not installed on this laptop — import guarded with `try/except` so tests pass.
* Follow-ups: Drop real `.pth` checkpoints, install `groundingdino`, `bitsandbytes` for Vicuna 4-bit, re-run `eval/evaluate.py --suite vrsbench/cdvqa` after Stage2 CDVQA training to enable `pipeline_mode: multimodal`.

## Verification

* `python -m pytest orchestrator/tests/test_real_models.py -v` 7 passed (singleton, 4 MODEL_LOAD_ERROR, no hardcoded confidence, contract shape)
* `python -m pytest orchestrator/tests/test_pipeline.py -v` 4 passed (vqa, change_vqa via error_handler, fusion via error_handler, CRS gate)
* `python -m pytest orchestrator/tests -v` 21 passed
* `npm --prefix frontend run build` 2574 modules 576ms
* `npm --prefix gateway run typecheck` pass (tsc --noEmit)
* `docker compose config` skipped (docker not installed on laptop, as in prior runs)
