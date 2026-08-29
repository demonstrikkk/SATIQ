"""Generate graph visualization — Mermaid + ASCII + optional PNG via graphviz."""
from __future__ import annotations
import os

MERMAID = """
```mermaid
flowchart TD
    START([START]) --> IV[input_validator\\nDeterministic gate\\nCRS hard check]
    IV -->|pass| R[router\\nMocked Qwen 3.5 9B]
    IV -->|fail| ERR[error_handler]
    R --> P[planner\\nMocked Qwen 3.5 9B • StepPlan]
    P --> PRE[preprocessing\\ntiling + dummy co-reg • writes tile_manager]
    P --> ES[encoder_selector\\nrule-based]
    ES --> EC[encoder_compat\\n gate]
    EC -->|fail| ERR
    EC -->|pass| BAR{{barrier_before_coreg<br/>join: preprocessing + encoder_compat}}
    PRE --> BAR
    BAR --> CG[coreg_gate\\nSSIM ≥0.75<br/>bypass if requires_coreg=false]
    CG -->|skip single-image| VE[vision_encoder\\nSatMAE/SSL4EO/Prithvi/CROMA dummy]
    CG -->|pass| VE
    CG -->|fail retry<2| PRE
    CG -->|fail max retries| ERR
    VE --> F[fusion\\n dummy attention]
    F --> TA[task_agent\\n VQA/Grounding/Change/Fusion]
    TA -- per-tile done --> TM[tile_manager<br/>state service: stitch_ready?]
    PRE -. tile creation .-> TM
    TM --> PP[post_processing\\n confidence gate + chart + stitch]
    PP -->|retry conf<0.6| TA
    PP -->|ok| RC[response_composer\\nMocked Qwen 3.5 9B]
    PP -->|fail| ERR
    RC --> END([END])
    ERR --> END
    TA -->|error| ERR
```
"""

MERMAID_ACTUAL_CODE = """
```mermaid
flowchart TD
    START --> IV[input_validator]
    IV -->|pass| R[router]
    IV -->|fail| ERR
    R --> P[planner]
    P --> PRE[preprocessing]
    PRE --> ES[encoder_selector]
    ES --> EC[encoder_compat]
    EC -->|pass| CG[coreg_gate\\n internal bypass if single-image]
    EC -->|fail| ERR
    CG -->|pass or skip| VE[vision_encoder]
    CG -->|fail retry<2| PRE
    CG -->|fail max| ERR
    VE --> F[fusion]
    F --> TA[task_agent]
    TA --> TM[tile_manager]
    TM --> PP[post_processing]
    PP -->|retry| TA
    PP -->|ok| RC[response_composer]
    PP -->|fail| ERR
    RC --> END
    ERR --> END
```
"""

ASCII = """
START
  → Input Validator (CRS hard gate)
    → (fail) → Error Handler → END
    → (pass) → Router (Mocked Qwen 3.5 9B) → Planner (Mocked Qwen 3.5 9B)
      → FAN-OUT (architectural intent):
        ├─ Preprocessing (tiling + dummy co-reg) ─┐
        └─ Encoder Selector (rule) → Encoder Compat ─┘
      → barrier_before_coreg (join) → Co-reg Gate (SSIM ≥0.75, bypass if requires_coreg=false)
        → (skip single-image VQA/grounding) → Vision Encoder
        → (pass) → Vision Encoder (dummy SatMAE/SSL4EO/Prithvi/CROMA)
        → (fail & retry<2) ↺ Preprocessing (direct, bypass barrier on retry)
        → (fail max) → Error Handler → END
        → Vision Encoder → Multimodal Fusion → Task-Specific Agent
          → Tile Manager (state service: preprocessing tile creation + task_agent per-tile done) → Post-Processing (conf gate + chart + stitch)
            → (retry conf<0.6, <3) ↺ Task Agent
            → (ok) → Response Composer (Mocked Qwen 3.5 9B) → END
            → (fail) → Error Handler → END
ACTUAL CODE EXECUTION (sequential for Pregel reliability):
  planner → preprocessing → encoder_selector → encoder_compat → coreg_gate (internal bypass) → vision_encoder ...
  See MERMAID_ACTUAL_CODE for LangGraph-generated PNG.
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
