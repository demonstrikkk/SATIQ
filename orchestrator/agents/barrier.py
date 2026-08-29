"""Barrier node for planner fan-out join — waits for preprocessing + encoder_compat."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace

def barrier_before_coreg_node(state: GraphState) -> GraphState:
    # Pregel already ensures both predecessors completed before this node runs
    # if planner fan-out is used (planner → preprocessing, planner → encoder_selector)
    # This node is a no-op join that confirms both branches done
    t0 = time.time()
    pd = state.get("preprocessing_done", False)
    er = state.get("encoder_ready", False)
    # Both should be True when barrier runs via join; if not, log but still proceed
    add_trace(state, "barrier_before_coreg", "ok", {"preprocessing_done": pd, "encoder_ready": er, "requires_coreg": state.get("requires_coreg")}, latency_ms=int((time.time()-t0)*1000))
    return state
