# Satiq — SatQuery AI

> **Zero-synthetic, fail-closed, 8-node LangGraph** execution engine powered strictly by **Ollama `qwen3.5:9b`** and real **PyTorch vision shims**. No mocks, no dummy bbox/confidence, no Groq fallback.

Chat-based geospatial QA over single-image, cross-modal Optical+SAR, and bi-temporal analysis. Deterministic input gate → Ollama tool-calling (10 tools) → 4 real capability shims → post-processing confidence & evidence grounding → streaming composer with auditable trace.

**Current state:** `Ollama qwen3.5:9b` only (`LLM_PROVIDER=local`), 8-node minimal graph (was 14), 4 pluggable shims under `models/model1..4` (do not edit inference scripts), single-GPU `VRAM_SEMAPHORE(2)` + `asyncio.to_thread`, 45s budget. See `docs/complete_system.mmd` / `orchestrator/graph/workflow_detailed.mmd` for live architecture.

---

## Quick Start — First Run (dev friend, no prior run)

```powershell
# 0) Preflight — proves wiring without docker/GPU/Ollama
powershell -ExecutionPolicy Bypass -File scripts/preflight.ps1
# or: make preflight  (same)
pytest tests/e2e/test_replay.py -v   # offline cassette, 6 cases, no Ollama

# 1. Ollama — qwen3.5:9b only (3–6s cold-start, then VRAM-resident)
ollama serve
ollama pull qwen3.5:9b
ollama run qwen3.5:9b "hi"   # must print hi

# 2. One command — full stack (compose)
docker compose up --build -d
# verify (diagnostic if 502/503)
curl http://localhost:8000/health            # -> {status healthy, ollama_reachable true, ollama_model qwen3.5:9b}
curl http://localhost:8000/api/v1/tools      # -> 10 tools (MODEL 4 + DETERMINISTIC 6)
# or dev (no docker):
# $env:PYTHONPATH="."; .\orchestrator\.venv\Scripts\python -m uvicorn orchestrator.api.main:app --host 0.0.0.0 --port 8000
# npm --prefix gateway run dev  # :4000 keepAlive 70s duplex:half 60s
# npm --prefix frontend run dev # :5173 (Composer 100MB createObjectURL, StreamMarkdown ?bbox=)
```

**Prereqs:** Python 3.11, Node 18+, Ollama, (optional) CUDA 12.1 for shims (`torch 2.2.2+cu121`), `ffmpeg` on PATH for CPU crop, `rasterio` for ingest. No Groq/Mistral keys needed. See `orchestrator/.env.example` (`QWEN_MODEL=qwen3.5:9b`, `QWEN_BASE_URL=http://localhost:11434/v1`).

**Weights (fail-closed if absent → `MODEL_NOT_LINKED`):** `models/model1/merged_model` (GeoChat-7B 13.5GB), `models/model2/pretrained/*.pth + config` (GroundingDINO Swin-T), `models/model3/pretrained/*.pth + checkpoints/stage1_final.pth` (Prithvi+Vicuna), `models/model4/fusion/{croma_base.pt,best_fusion_model.pt}` + vendored `engine.py`/`data/preprocessing.py`. Add checkpoints — pipeline returns `MODEL_NOT_LINKED` (permanent) until present; no dummy.

```powershell
# One-command weights (huggingface_hub, HF_TOKEN for gated models)
python scripts/download_weights.py --dry-run   # list URLs
python scripts/download_weights.py --model all  # pull all 4 (needs ~25GB)
python scripts/download_weights.py --check     # verify MODEL_NOT_LINKED clears
# or: make weights  |  make weights-check
```

---

## 1. Input Configurations

| # | Configuration | Modality / Assets | Example Query | Task |
|---|---------------|-------------------|---------------|------|
| 1 | **Single Image** | 1× optical/multispectral/SAR (`crs`+`gsd` required) | "What land cover is present? Count built-up clusters." | `vqa` |
| 2 | **Cross-Modal Pair** | Optical + SAR co-registered same AOI | "Identify crop and water using optical+SAR" | `optical_sar_fusion` |
| 3 | **Bi-Temporal Pair** | t1 + t2 same AOI, different dates | "Has built-up increased? What changed and where?" | `change_vqa` |
| — | **Grounding** | 1× optical + referring expression | "Where is the water body in the north?" | `grounding` → bbox + `?bbox=` URL → MapLibre |
| — | **Definitional** | 0 images, geospatial knowledge | "What is NDVI?" | `chitchat` (skip_models) |

> GeoTIFF/TIFF required for production; PNG/JPEG only for benchmarks.

---

## 2. Architecture — 8-Node Minimal

```mermaid
flowchart TB
    U[User query + images] --> FE[Frontend 5173<br/>Composer 100MB createObjectURL<br/>StreamMarkdown ?bbox=]
    FE --> GW[Gateway 4000<br/>upload duplex:half 60s + query agentic dedup 32]
    GW --> ING[POST /api/v1/ingest<br/>EXIF GPS + validate_geotiff]
    GW --> TASK[POST /api/v1/task<br/>_normalize_assets • CRS 400 • 100Mpix 413 • queue 429<br/>Redis satiq:exec:{id} 3600 + Last-Event-ID]
    TASK --> IV[input_validator<br/>request_key sorted-hash • deadline 45s<br/>len 16-4000 • jailbreak guardrails<br/>CRS hard gate • GSD>0 • 100Mpix]
    IV -->|fail| EH[error_handler]
    IV -->|pass| CR[coreference_resolver<br/>entity_registry • history]
    CR --> R[router<br/>Ollama ROUTER_TOOLS 4<br/>tool_choice auto via to_thread]
    R --> P[planner<br/>Ollama REGISTERED_TOOLS 10 + RAG<br/>PlanSchema • guardrails step cap 10]
    P -->|skip greeting/chitchat/help| RC[response_composer<br/>Ollama stream 2048]
    P -->|geospatial| TA[task_agent<br/>VRAM 2 • to_thread → shim]
    TA --> S1[model1 GeoChat-7B<br/>ask_geochat]
    TA --> S2[model2 GroundingDINO<br/>2-98% percentile → bbox]
    TA --> S3[model3 Prithvi+Vicuna<br/>indices + fusion]
    TA --> S4[model4 CROMA 12+2<br/>Model4Engine]
    TA --> PP[post_processing<br/>conf 0.6 • bbox [0,1] • chart real only]
    PP --> RC
    PP -->|retry ×3| TA
    RC --> SSE[SSE answer_delta → Gateway → Frontend<br/>+ /api/assets bbox overlay]
    EH --> END
    RC --> END
```

Live, code-accurate diagrams: `orchestrator/graph/complete_system.mmd` (layered) + `orchestrator/graph/workflow_detailed.mmd` (wired workflow) + PNGs `complete_system.png 2400×3300` / `workflow_detailed.png 2400×~2450` via `python orchestrator/graph/workflow_detailed.py` (Pillow). Premium HTML: `docs/workflow_premium.html`.

### 2.1 Input Handler — Deterministic Gate (no LLM cost)
File `agents/input_validator.py:23` + `helpers/guardrails.py`, `services/image_ingest.py`
- Length 16–4000, empty/greeting/out_of_scope via LLM (no `4x+3y` literals), jailbreak `check_prompt_injection`
- CRS hard gate `_crs_mismatch` (permanent), `GSD>0`, `w*h>100Mpix` guard, `_corrupt/malformed_geotiff`
- `request_key` sorted-hash + `deadline_ms = now+45s`, `node_latencies`, `retry_policy`, `circuit_breaker_state`
- `POST /api/v1/ingest` ingest: `rasterio→PIL` validate, EXIF GPS, thumbnail, `orchestrator/storage/ingest/<stem>.tif` (no resampling before model)

### 2.2 Ollama Tool-Calling — Router & Planner
Files `core/llm_client.py:500` + `helpers/tool_schemas.py:13` + `agents/router_agent.py:11` + `agents/planner_agent.py:9`
- **Ollama `qwen3.5:9b` only** — `LLM_PROVIDER=local`, `resolve_provider` raises if not `has_local_qwen_capability()` (no Groq/Mistral/mock)
- `ROUTER_TOOLS 4` + `REGISTERED_TOOLS 10` (`run_vqa/grounding/change_vqa/fusion` + `compute_spectral_indices/calculate_area/geocode_region/crop_bbox/generate_visual_evidence/retrieve_history`) via `ollama.chat tools=... tool_choice auto`, `TOOL_NAME_TO_TASK` mapping, else single-word `vqa|grounding|change_vqa|optical_sar_fusion|greeting|chitchat|help|out_of_scope`
- `registry/capability_registry.py` `validate_legality` + `guardrails.validate_plan` hard block `capability_illegal/step cap 10` (PlanSchema)

### 2.3 Single-GPU Execution + Off-GPU Crop
File `agents/task_agents.py:34` + `capabilities/model_adapter.py:20` + `services/image_pipeline.py` + `services/ffmpeg_preprocessor.py:14`
- `VRAM_SEMAPHORE(2)` + `asyncio.to_thread(call_model, ...)` — models bundle own encoders (CLIP/Swin/Prithvi/CROMA), no external tiles
- `resolve_asset` sanitizes `asset_/file_` → `rglob` `gateway/upload`↔`storage/ingest`, **no resampling** before shim
- `FFmpeg crop_bbox_to_png` CPU `-vf crop=w:h:x:y,scale=512` (grounding only, `last_crop_path`), `tiling 512+64 Window` via `rasterio` or passthrough, `spectral NDVI/NDWI/NDBI/EVI` pure numpy (dummy→raise), `geocoder BUILTIN_GAZETTEER`
- **Abort propagation:** `if EXECUTIONS[session_id].get("is_cancelled"): return` before `VRAM_SEMAPHORE` (saves GPU slot)
- **CUDA flush:** `finally: torch.cuda.empty_cache(); gc.collect()` after each shim

### 2.4 Response Composer — Streaming
File `agents/response_composer.py` + `core/llm_client.py` `call_qwen_composer_stream` (Ollama `stream True`, 2048 tok), `helpers/chart_spec.py`.
- Emits `thinking_delta/answer_delta`, `chart` ```chart, `bbox` table + normalized `?bbox=x1,y1,x2,y2` on `/api/assets/{name}` (768px, not base64) → `StreamMarkdown` MapLibre overlay (no keyword heuristic)
- `save_history` fire-and-forget → `rag_store Chroma 8001/chroma_data` + `SQLite memory.db` + `audit.db execution_traces` + `MinIO rs-outputs`

---

## 3. The 4 Shims — Real Weights, Fail-Closed

| Shim | Model | Input → Output | Shim file |
|------|-------|----------------|-----------|
| **model1 VQA** | GeoChat-7B merged 13.5GB (4bit 7GB) | `image_path + query` → `ask_geochat` → `{text, confidence:None}` | `capabilities/shims/model1_shim.py` → `models/model1/run_inference.py` |
| **model2 Grounding** | GroundingDINO Swin-T ~170M | `image_path + query` → `load_and_convert_s2 2-98%` → `build_groundingdino` → `bbox_xyxy` pixel + `bbox_normalized [0,1]` + `scores` | `shims/model2_shim.py` → `models/model2/visualize_pipeline_graph.py` + vendor `config.py/train.py` (do not edit inference) |
| **model3 Change** | Prithvi-100M + Vicuna-7B hybrid | `t1 + t2 + query` → `compute_indices` NDVI/NDBI/NDWI (fail-closed B04/B08) → `classify_deltas 0.05` → `fusion_change_confidence` → Vicuna text-only | `shims/model3_shim.py` → `models/model3/visualize_index_hybrid.py` |
| **model4 Fusion** | CROMA dual ViT 12+2 120×120 cross-attention | `optical + sar + query` → `Model4Engine.predict` → `per_modality + spatial_cam` | `shims/model4_shim.py` → `models/model4/infer.py` + vendor `engine.py/data/preprocessing.py` |

`capabilities/model_adapter.py:20` `MODEL_MAP` shim-pref (`probe inference/ask_geochat`, wrap `str→dict`), `is_model_linked` checks shim+original, missing → `MODEL_NOT_LINKED` permanent, inference exception → `MODEL_INFERENCE_ERROR` transient (retry 1). `config.py` `models_root=models` relative, `validated_gateway_url()` at 4 sites, no `C:/coding/sih`.

---

## 4. Repository Structure

```
satiq/
├── frontend/                    # React + TS + MapLibre
│   ├── src/components/chat/     # Composer 100MB createObjectURL, StreamMarkdown ?bbox=, ChartBlock ApexCharts
│   ├── src/lib/analysisClient.ts # abort-safe SSE, Finally only if !failed
│   └── public/complete_system.png
├── gateway/                     # Node/Express + TS :4000
│   ├── src/routes/upload.ts     # createReadStream duplex:half 60s + _authHeader
│   ├── src/analysis/providers/agentic-analysis.provider.ts # dedup 32 + keepAlive 70s
│   └── upload/                  # ephemeral — TTL cleanup 1h
├── orchestrator/                # Python :8000 FastAPI + LangGraph 8-node
│   ├── graph/pipeline.py        # 8 nodes, after_planner skip_models → composer
│   ├── agents/                  # input_validator, coreference, router, planner, task_agents, post_processing, response_composer, error_handler
│   ├── capabilities/shims/      # model1..4 thin wrappers (do not edit models/model*/inference)
│   ├── models/model2/config.py  # vendored IMAGE_SIZE 224, RGB_BANDS, PRETRAINED_DIR
│   ├── models/model4/engine.py  # vendored Model4Engine singleton + preprocessing
│   ├── helpers/tool_schemas.py  # REGISTERED_TOOLS 10 + ROUTER_TOOLS 4
│   ├── helpers/guardrails.py    # PlanSchema + validate_plan
│   ├── services/                # image_pipeline, ffmpeg_preprocessor, spectral, geocoder, tiling 512+64, transcription (no mock)
│   ├── memory/rag_store.py      # Chroma satiq_conversation 8001
│   ├── core/llm_client.py       # Ollama qwen3.5:9b only, no Groq
│   └── graph/complete_system.*  # layered + workflow_detailed 2400×~2450 PNG (Pillow)
├── models/model1..4/            # mounted read-only, inference scripts do not edit
│   ├── model1/run_inference.py  # GeoChat
│   ├── model2/visualize* + vendor config/train
│   ├── model3/visualize_index_hybrid.py
│   └── model4/infer.py + vendor engine/data
├── docker-compose.yml           # + chroma:8001 & models:ro & CHROMA_HOST
└── docs/                        # DECISIONS.md + PROGRESS.md + workflow_premium.html
```

---

## 5. Mandatory Requirements → How Satiq Satisfies Them

| Requirement | Satisfied By |
|-------------|--------------|
| **RS adaptation** | Real weights via shims (BigEarthNet S1+S2), not COCO; `ModelManager` singleton, thread-safe |
| **Grounding** | Model2 bbox `[0,1]` pixel + `?bbox=` URL → MapLibre (no dummy) |
| **Change** | Model3 `t1+t2` + `?bbox` region_of_interest via geocoder, sub_queries merger |
| **Optical-SAR fusion** | Model4 12+2 `Model4Engine`, `per_modality` + `spatial_cam` |
| **Agentic orchestration** | 8-node LangGraph, function-calling (`tool_choice auto`), `PlanSchema` guardrails, `max_transient 2` |
| **Input compatibility** | CRS hard gate + GSD + 100Mpix + jailbreak + pairing temporal/contrast via `query_analyzer` |
| **Auditable trace** | `execution_trace` + `thinking_delta` + `events` SSE + `audit.db` + `chart` + `artifacts` |

---

## 6. Tech Stack

| Layer | Choice |
|-------|--------|
| **Frontend** | React + TypeScript + Vite, MapLibre GL, ApexCharts, Zustand `satiq-chat-v1` (quota-safe `partialize` strips preview) |
| **Gateway** | Node/Express + TS, `keepAlive 70s`, `randomUUID` + `.jp2` |
| **Orchestrator** | Python 3.11 FastAPI + LangGraph, Ollama `qwen3.5:9b` via `ollama` + OpenAI-compat `http://localhost:11434/v1`, Pydantic |
| **Vision** | GeoChat-7B, GroundingDINO Swin-T, Prithvi+Vicuna, CROMA — vendored shims |
| **Memory/RAG** | Chroma 0.5.20 + `llama-index 0.11.20` + SQLite `memory.db`, `TTLCache 3600/1024` |
| **Storage** | MinIO 9000 `rs-outputs` + disk fallback `orchestrator/storage/ingest`, `reportlab` PDF |
| **Infra** | `docker-compose` + `chroma` service, `models:ro` mount, `lifespan` warmup |

---

## 7. Build Priority (Done → Next)

1. **✅ Pydantic `raster_asset` + `analysis_result` + CRS hard gate**
2. **✅ Model4 CROMA + Model3 Change hybrid (index + fusion)**
3. **✅ Model1 VQA + Model2 Grounding (vendors)**
4. **✅ Orchestrator 8-node + Ollama tool-calling + guardrails**
5. **✅ Composer streaming + charts + bbox URL + RAG**
6. **✅ Frontend/Gateway hardening (upload stream, abort, keepAlive)**
7. **Next:** `evaluation/evaluate.py --suite vrsbench` (VRSBench/RSVQA/CDVQA) after dropping checkpoints; `adaptation/train.py` LoRA.

---

## 8. Lifespan & Resilience (implemented)

- **Lifespan warmup** (`api/main.py:567`): `ollama.chat(model=qwen3.5:9b, 1-token)` on startup + `has_local_qwen_capability` check — cold-start 3–6s absorbed before first query, stays in 45s budget.
- **Abort propagation** (`agents/task_agents.py:34`): `if EXECUTIONS[session_id].get("is_cancelled"): return` before `VRAM_SEMAPHORE` — cancels orphaned `to_thread` slot.
- **Disk cleanup** (`services/image_ingest.py:246` + `gateway/upload`): `mtime>3600` sweep of `orchestrator/storage/ingest/*` + `gateway/upload/*` + FFmpeg `/tmp/crop_*.png`.
- **CUDA flush** (`agents/task_agents.py:22`): `finally: torch.cuda.empty_cache(); gc.collect()` after each shim.
- **Bbox URL** (`agents/task_agents.py:70` + `api/main.py:233`): `?bbox=x1,y1,x2,y2&crs=EPSG:4326` on `/api/assets` → `StreamMarkdown` `bbox://` without keyword heuristic (was `water→0.18` removed).
- **Redis TTL** (`api/main.py:105`): `satiq:exec:{id} setex 3600` + `Last-Event-ID id:` replay.

---

## 9. Evaluation

```bash
python evaluation/evaluate.py --suite vrsbench   # VQA + grounding + captioning
python evaluation/evaluate.py --suite rsvqa
python evaluation/evaluate.py --suite cdvqa
# reports → evaluation/reports/
```

Requires linked weights; otherwise `MODEL_NOT_LINKED` permanent (auditable, not dummy).

---

**License:** TBD · **Status:** Ollama-only demo ready — `workflow_premium.html` for premium architecture view.
