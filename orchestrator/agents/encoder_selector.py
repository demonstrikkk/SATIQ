"""Agent 4: Encoder Selector — rule-based, no LLM."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace

def encoder_selector_node(state: GraphState) -> GraphState:
    t0 = time.time()
    task_type = state.get("task_type","vqa")
    assets = state.get("assets") or []
    # heuristic: infer modality from assets
    modalities = [a.get("modality","unknown") for a in assets]
    has_sar = "sar" in modalities
    has_optical = any(m in ("optical","multispectral") for m in modalities)
    # selection logic
    if task_type == "optical_sar_fusion" and has_sar and has_optical:
        encoder = "croma"
    elif task_type == "change_vqa":
        encoder = "prithvi"  # bi-temporal FM
    elif task_type == "grounding":
        encoder = "satmae"
    elif task_type == "vqa":
        # choose ssl4eo for multispectral else satmae
        if has_optical and len(modalities)==1 and modalities[0]=="multispectral":
            encoder = "ssl4eo"
        else:
            encoder = "satmae"
    else:
        encoder = "satmae"

    state["encoder"] = encoder
    add_trace(state, "encoder_selector", "ok", {"encoder": encoder, "modalities": modalities, "task": task_type}, latency_ms=int((time.time()-t0)*1000))
    return state
