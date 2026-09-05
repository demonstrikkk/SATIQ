# Friend Handoff — How to Link Inference Scripts & Edit Satiq Safely

> Give this file to your dev friend. They `docker compose up --build` on their machine — you cannot run locally, so first-run must be fail-fast and diagnosable.

## 1. How Linking Works (do not rename originals)

Satiq **never edits** your 4 originals. A thin **shim** wraps each:

| Task | Original (frozen) | Shim to edit |
|------|-------------------|--------------|
| `vqa` / `captioning` | `models/model1/run_inference.py` (`load_model` + `ask_geochat`) | `orchestrator/capabilities/shims/model1_shim.py` |
| `grounding` | `models/model2/visualize_pipeline_graph.py` (`load_and_convert_s2` + `build_groundingdino` + `run_inference`) | `orchestrator/capabilities/shims/model2_shim.py` |
| `change_vqa` | `models/model3/visualize_index_hybrid.py` (`compute_indices` + `classify_deltas` + `fusion_change_confidence`) | `orchestrator/capabilities/shims/model3_shim.py` |
| `optical_sar_fusion` | `models/model4/infer.py` + `models/model4/engine.py` + `models/model4/data/preprocessing.py` (`Model4Engine.predict`) | `orchestrator/capabilities/shims/model4_shim.py` |

Routing: `orchestrator/capabilities/model_adapter.py:15` `MODEL_MAP` checks **shim exists AND original exists** → `is_model_linked(task)==True`. `call_model(task, query, image_paths)` probes shim `inference|run|predict|infer|call|ask_geochat|run_inference` and passes **raw `image_path` as-is** (no resampling/radiometry before model).

- Missing file → `MODEL_NOT_LINKED` **permanent** (friend sees `permanent error: MODEL_NOT_LINKED ...` in response, not a silent dummy).
- Shim throws → `MODEL_INFERENCE_ERROR` **transient** (retried once, cap `MAX_REFLECTION_ITERATIONS=2` in `orchestrator/graph/pipeline.py:45`).
- Confidence: return `None` if model has no score (e.g., GeoChat). `orchestrator/agents/post_processing.py:17` treats `None` as honest pass, no `0.82` invention. Bbox is clamped `[0,1]` there.

Single-GPU guard: `VRAM_SEMAPHORE(2)` + `asyncio.to_thread` in `orchestrator/agents/task_agents.py` — keep inference inside shim.

Weights are **local-only, not in git** (30 GB). Mount read-only via `docker-compose.yml: orchestrator volumes ./models:/app/models:ro`. Expected paths (see `README.md` Weights):

```
models/model1/merged_model/          # GeoChat-7B 13.5 GB (config.json + pytorch_model.bin)
models/model2/pretrained/*.pth       # GroundingDINO Swin-T + config (config.py PRETRAINED_DIR)
models/model3/pretrained/*.pth
models/model3/checkpoints/stage1_final.pth
models/model4/fusion/croma_base.pt
models/model4/fusion/best_fusion_model.pt
```

Until those are placed, `scripts/preflight.ps1` warns `MODEL_NOT_LINKED` — correct behavior.

## 2. Invariants Friend Must Not Break

- **Ollama `qwen3.5:9b` only** (`orchestrator/core/config.py` `QWEN_MODEL`, `LLM_PROVIDER=local`). No Groq/Mistral keys.
- **8-node DAG** `input_validator → coreference → router → planner → task_agent → post_processing → error_handler → response_composer` (`orchestrator/graph/pipeline.py`). Cap 2 reflections protects `45s` `orchestrator/core/timeouts.py:22` `TOTAL_BUDGET=45000`.
- **Hard gates**: `100Mpix` (`input_validator.py`), CRS mismatch → `400` before LLM, `allow_synthetic_assets=false` (prod).
- **10 strict tools** `orchestrator/helpers/tool_schemas.py` (MODEL 4 + DETERMINISTIC 6). Observe via `GET /api/v1/tools`.

## 3. Copy-Paste Prompt for Codex / Cursor / Muse Spark

> Paste this verbatim when asking an AI to edit Satiq on your friend's machine:

```
You are editing Satiq (SatQuery AI) at C:\path\to\Satiq. Constraints:

1. DO NOT edit models/model1/run_inference.py, models/model2/visualize_pipeline_graph.py, models/model3/visualize_index_hybrid.py, models/model4/infer.py — they are frozen originals with their weights.
2. Edit ONLY orchestrator/capabilities/shims/model{1..4}_shim.py to adapt signatures. Shim contract:
   - vqa/grounding: def inference(image_path: str, query: str) -> dict
   - change_vqa:    def inference(image_t1: str, image_t2: str, query: str) -> dict
   - fusion:        def inference(optical_path: str, sar_path: str, query: str) -> dict
   Return {text, answer_text, confidence: float|None, bbox_xyxy|bbox_normalized?, artifacts, metadata}. Never invent confidence — return None if model has no score. Bbox clamped [0,1] in post_processing.
3. model_adapter.py MODEL_MAP already maps task->file->shim. Use is_model_linked(task) to verify. Keep call_model probing order inference|run|predict|ask_geochat.
4. Weights are local only (not in git): model1/merged_model 13.5GB, model2/pretrained/*.pth, model3/pretrained + checkpoints/stage1_final.pth, model4/fusion/croma_base.pt + best_fusion_model.pt. Mount via docker-compose volumes ./models:/app/models:ro.
5. System invariants: 8-node LangGraph pipeline.py MAX_REFLECTION_ITERATIONS=2, input_validator 100Mpix guard, CRS hard gate, TOTAL_BUDGET 45000, Ollama qwen3.5:9b only (no Groq). Post-processing caps: bbox clamp [0,1], no dummy sectors.
6. Verify without full GPU:
   python -m py_compile orchestrator/capabilities/shims/*.py orchestrator/capabilities/model_adapter.py orchestrator/helpers/guardrails.py orchestrator/graph/pipeline.py orchestrator/api/main.py
   pytest tests/e2e/test_replay.py -v  (offline, 7 tests, no Ollama)
   powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1  (shows MODEL_NOT_LINKED until weights linked)
   curl http://localhost:8000/health  (ollama_reachable)
   curl http://localhost:8000/api/v1/tools  (10 tools)
7. Every code change must also touch docs/DECISIONS.md + docs/PROGRESS.md (AGENTS.md §8) and include an ADR if behavior/data/dep changes.

Task: <describe your change here — e.g., "adapt model2 shim for new Swin-T checkpoint path models/model2/pretrained/gdino_swin_t_ogc.pth" or "wire models/model3/inference.py alternative entry">
```

## 4. First-Run Checklist (friend, 3 minutes)

```powershell
# 0) prove wiring without docker/GPU/Ollama
powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1
# expect: [OK] py_compile true, [OK] cassette 6 samples, [WARN] MODEL_NOT_LINKED until weights placed

pytest tests/e2e/test_replay.py -v   # 7 passed offline

# 1) Ollama — qwen3.5:9b only
ollama serve                         # separate terminal
ollama pull qwen3.5:9b
ollama run qwen3.5:9b "hi"            # must print hi

# 2) weights — drop into exact paths above, not renamed

# 3) full stack
docker compose up --build -d
curl http://localhost:8000/health            # -> {status healthy, ollama_reachable true, qwen_model qwen3.5:9b}
curl http://localhost:8000/api/v1/tools      # -> {count 10, tools [...]}
# open http://localhost:3000 (frontend) / http://localhost:4000 (gateway)

# 4) if 502/503 — run preflight again; check `ollama_reachable`, `MODEL_NOT_LINKED`, and 100Mpix asset guard
```

## 5. Common Edits (safe)

- New checkpoint filename → edit shim's `Path(cfg).` lookup, not original `train.py`/`config.py`.
- Different function name (`predict` not `inference`) → shim's `inference()` wrapper calls `import run_inference as m1; m1.predict(img, query)`.
- Single image path is a dir with `*_B*.tif` → shim already handles `load_and_convert_s2` percentile 2–98; leave as-is.
- Do not add resampling/radiometric fix before `call_model` — adapter passes raw path intentionally.

Questions? Check `docs/adr/0008-pipeline-redesign-shims.md` (8-node + shims) and `docs/adr/0009-bounded-agentic-execution.md` (caps, cassette, health).
