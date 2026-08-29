# Satiq Orchestrator — RS-VLM Agentic Pipeline

> Implements the complete LangGraph RS-VLM pipeline with **Qwen 3.5 9B via Ollama** (OpenAI-compatible) and dummy vision encoders.

## Start (local, no Docker)

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt

# optional: ensure Ollama is running and Qwen model is available
# ollama pull qwen3:8b   # user said don't download for now — will fallback to heuristic
# set QWEN_MODEL=qwen3:8b if you have it, else dummy heuristic is used

uvicorn orchestrator.api.main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

- `POST /api/v1/task` — body: `{"query": "...", "image_ids": ["img_001"], "assets": [{"asset_id":"...","crs":"EPSG:32617"}]}` → `{"session_id":"sess_...","status":"queued"}`
- `GET /api/v1/task/{session_id}` — status + result + trace
- `WS  /ws/task/{session_id}` — streaming events (input/planner/model/evidence/composer)
- `GET /health`

Gateway-compatible aliases: `POST /api/query`, `GET /api/query/{id}`

## Tests

```bash
python -m pytest orchestrator/tests -v
# or individual:
python orchestrator/tests/test_validator.py
python orchestrator/tests/test_dummy_models.py
python orchestrator/tests/test_pipeline.py
python orchestrator/scripts/run_pipeline_demo.py
python orchestrator/graph/visualize.py
```

## Pipeline Graph

See `orchestrator/graph/graph.mmd` (Mermaid) and `orchestrator/graph/graph.png` (rendered).

```
START → Input Validator (CRS hard gate) → Router (Qwen) → Planner (Qwen) → Preprocessing → Encoder Selector → Encoder Compat → Co-reg Gate → Vision Encoder (dummy) → Fusion (dummy) → Task Agent (VQA/Grounding/Change/Fusion) → Tile Manager → Post-Processing (conf gate) → Response Composer (Qwen) → END
```

Conditional retries:
- Co-reg fail (SSIM<0.75) → retry Preprocessing max 2
- Low confidence (<0.6) → retry Task Agent max 3
- Any error → Error Handler → END

## Dummy Models

All vision is dummy, swappable in `orchestrator/dummy/`:
- `run_satmae` 1024-d, `run_ssl4eo` 768-d, `run_prithvi` 768-d, `run_croma`
- `run_fusion` (attention/concat)
- `dummy_vqa`, `dummy_grounding`, `dummy_change_vqa`, `dummy_optical_sar_fusion` — return exact JSON spec from prompt.

Replace these 4 files when real checkpoints arrive; pipeline unchanged.

## Qwen 3.5 9B

Via Ollama OpenAI-compatible endpoint (`QWEN_BASE_URL=http://localhost:11434/v1`). If Ollama unavailable, falls back to deterministic heuristic router/planner/composer (auditable, logged).

## Storage / Infra

- Postgres+PostGIS (SQLAlchemy models in `orchestrator/db/models.py`)
- Redis (session state `session:{sid}:*` TTL 3600) with in-memory fallback
- MinIO (buckets `rs-raw/rs-processed/rs-outputs/rs-models`) with local-disk fallback `orchestrator/storage/`
- Celery queues: `preprocess, inference.encode, inference.fusion, inference.task, postprocess, satellite.fetch` (see `orchestrator/core/celery_app.py`)

## CRS Safety

`orchestrator/ingestion/validator.py` is hard gate — EPSG mismatch returns 400 before LLM. Tested in `test_validator.py`.
