"""Agent 9: Multimodal Fusion."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.dummy.dummy_fusion import run_fusion

def fusion_node(state: GraphState) -> GraphState:
    t0 = time.time()
    # retrieve raw embeddings
    raw = state.get("_embeddings_raw") or state.get("embeddings") or {}
    # unwrap if wrapped
    if isinstance(raw, dict) and any(isinstance(v, dict) and "_raw" in v for v in raw.values()):
        # reconstruct raw from wrapped - use _embeddings_raw if exists
        raw = state.get("_embeddings_raw", raw)
    query = state.get("query","")
    plan = state.get("plan") or {}
    method = "attention"
    if state.get("task_type") == "optical_sar_fusion":
        method = "attention"
    elif state.get("encoder") == "croma":
        method = "attention"
    fused = run_fusion(raw, query, method=method)
    state["fused_repr"] = fused
    add_trace(state, "fusion", "ok", {"method": method, "confidence": fused.get("confidence"), "dim": fused.get("dim")}, latency_ms=int((time.time()-t0)*1000))
    return state
