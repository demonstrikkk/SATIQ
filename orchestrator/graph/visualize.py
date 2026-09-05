"""Generate graph visualization — Mermaid + ASCII + optional PNG via graphviz."""
from __future__ import annotations
import os

MERMAID = """
```mermaid
flowchart TD
    %% 8-node LangGraph state graph: 7 happy + terminal error_handler (cross-cutting failure sink, not linear step) — bounded retry MAX_ATTEMPTS=2
    START([START]) --> IV[input_validator<br/>Deterministic gate<br/>CRS hard check • GSD>0 • 100Mpix • 16-4000 chars • jailbreak • deadline_at authoritative 45s]
    IV -->|fail| ERR[error_handler]
    IV -->|pass| CR[coreference_resolver<br/>resolve [RESOLVED:bbox] • entity_registry 4-tier]
    CR --> R[router<br/>Ollama qwen3.5:9b ROUTER_TOOLS 4<br/>ollama.chat tool_choice auto via to_thread]
    R --> P[planner<br/>Ollama qwen3.5:9b REGISTERED_TOOLS 10 + registry + RAG 4-tier hybrid<br/>PlanSchema • guardrails • step cap 10 • success_condition]
    P -->|skip_models=greeting/chitchat/help/out_of_scope| RC[response_composer<br/>Ollama qwen3.5:9b stream 2048 tok]
    P -->|geospatial| TA[task_agent<br/>VRAM_SEMAPHORE 2 + queue 4 → 503 • asyncio.to_thread<br/>shim model1/2/3/4 + reproject_to_target warp • CPU crop]
    TA -->|MODEL_NOT_LINKED permanent| ERR
    TA -->|queue_full 503 permanent| ERR
    TA -->|MODEL_INFERENCE_ERROR transient retry 1| TA
    TA -->|ok| PP[post_processing<br/>conf≥0.6 • bbox clamp [0,1] • evidence grounding • chart real only]
    PP -->|retry conf<0.6 <2| TA
    PP -->|fail| ERR
    PP -->|ok| RC
    RC --> END([END])
    ERR[error_handler<br/>cross-cutting terminal<br/>any node → ERR → response_composer] --> END
    TA -. image_path via image_pipeline.resolve_asset + reproject warp .-> SHIMS[""model1: GeoChat-7B<br/>model2: GroundingDINO Swin-T<br/>model3: Prithvi+Vicuna<br/>model4: CROMA"}}
    SHIMS -. raw image + query .-> TA
    P -. RAG retrieve_for_planner .-> MEM[(Memory 4-tier<br/>working + episodic hybrid 0.7/0.3 + semantic)]
    TA -. metrics p50/p99 + vram .-> MON[(metrics)]
```
"""

MERMAID_ACTUAL_CODE = """
```mermaid
flowchart TD
    START --> IV[input_validator]
    IV -->|pass| CR[coreference_resolver]
    IV -->|fail| ERR[error_handler]
    CR --> R[router]
    R --> P[planner]
    P -->|skip_models| RC[response_composer]
    P -->|geospatial| TA[task_agent<br/>via shims]
    TA -->|ok| PP[post_processing]
    TA -->|error| ERR
    PP -->|retry| TA
    PP -->|ok| RC
    PP -->|fail| ERR
    RC --> END
    ERR --> END
```
"""

ASCII = """
CURRENT SYSTEM (8-node LangGraph state graph: 7 happy + terminal error_handler, MAX_ATTEMPTS=2 total — Ollama qwen3.5:9b ONLY)

START
  → Input Validator (CRS hard gate • GSD>0 • 100Mpix • 16-4000 chars • jailbreak • request_key/deadline 45s wait_for, budget enforced)
    → (fail permanent: empty_query/greeting/out_of_scope/too_long/too_short/injection/crs_mismatch/malformed) → Error Handler → END
    → (pass) → Coreference Resolver (alias → [RESOLVED:bbox] from entity_registry + ts, 4-tier working <1k)
      → Router (Ollama qwen3.5:9b ROUTER_TOOLS 4 via to_thread)
        → Planner (Ollama qwen3.5:9b REGISTERED_TOOLS 10 + registry + RAG 4-tier retrieve_for_planner hybrid 0.7/0.3 + decay, PlanSchema success_condition step cap 10)
          → (skip_models: greeting/chitchat/help/out_of_scope/REFUSE) → Response Composer (Ollama stream 2048, thinking_delta)
          → (geospatial: vqa/grounding/change_vqa/optical_sar_fusion) → Task Agent (VRAM_SEMAPHORE 2 + queue 4 → 503 + queue_position SSE, to_thread → shim + reproject_to_target EPSG:4326 warp + crop)
            → model1_shim: GeoChat-7B → ask_geochat → {text,confidence:None}
            → model2_shim: GroundingDINO 2-98% → run_inference → bbox_xyxy + bbox_normalized
            → model3_shim: Prithvi indices+fusion + Vicuna
            → model4_shim: CROMA 12+2 → per_modality
            → (queue_full 503 permanent → Error Handler; MODEL_NOT_LINKED permanent; MODEL_INFERENCE_ERROR transient→retry 1)
            → Post-Processing (conf≥0.6, bbox [0,1], chart real only, evidence grounding, <2 retries)
              → (retry <2) ↺ Task Agent
              → (fail) → Error Handler
              → (ok) → Response Composer → END
          → Error Handler → END

Paths: Composer 100MB createObjectURL → gateway/upload duplex:half 60s (.geotiff/.gtiff/.jp2) → orchestrator/storage/ingest + image_pipeline.resolve_asset + reproject warp → shim raw path. Memory: working 3 + episodic hybrid (vector+BM25+decay, where=session_id, 90d) + semantic (180d consolidation) + state Redis 1h. Metrics: p50/p95/p99 + vram peak/queue. Weights: scripts/download_weights.py --model all (HF_TOKEN).
"""

def save_mermaid(path: str = "orchestrator/graph/graph.mmd"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(MERMAID)
    return path

def save_ascii(path: str = "orchestrator/graph/graph.txt"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(ASCII)
    return path

def try_png_via_langgraph(path: str = "orchestrator/graph/graph.png"):
    """Try LangGraph's built-in draw_mermaid_png if available."""
    try:
        from orchestrator.graph.pipeline import get_pipeline
        g = get_pipeline()
        # get_graph().draw_mermaid_png() requires mermaid + graphviz or api
        png = g.get_graph().draw_mermaid_png()  # type: ignore
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(png)
        return path
    except Exception as e:
        return f"PNG not generated (needs graphviz/mermaid.ink): {e}"

if __name__ == "__main__":
    print(save_mermaid())
    print(save_ascii())
    print(try_png_via_langgraph())
    print(MERMAID)
    print(ASCII)
