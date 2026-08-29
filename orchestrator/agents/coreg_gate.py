"""Agent 7: Co-reg Quality Gate — conditional retry."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace

def coreg_gate_node(state: GraphState) -> GraphState:
    t0 = time.time()
    # Bypass for single-image tasks (requires_coreg == false) per cross-verification fix #5
    if not state.get("requires_coreg", False):
        state["coreg_passed"] = True
        add_trace(state, "coreg_gate", "skipped", {"reason": "requires_coreg=false (single-image VQA/grounding/captioning) bypass", "task_type": state.get("task_type")}, latency_ms=int((time.time()-t0)*1000))
        return state
    coreg = state.get("coreg") or {}
    ssim = coreg.get("ssim", 1.0)
    residual = coreg.get("residual", 0.0)
    passed = coreg.get("passed", True)
    # threshold from ethics: ssim>=0.75 and residual<=0.6
    if not passed:
        state["coreg_passed"] = False
        # increment retry counter
        state["coreg_retries"] = state.get("coreg_retries", 0) + 1
        add_trace(state, "coreg_gate", "failed", {"ssim": ssim, "residual": residual, "retries": state["coreg_retries"]}, latency_ms=int((time.time()-t0)*1000))
        # error log
        state.setdefault("error_log", []).append(f"coreg failed ssim={ssim} residual={residual}")  # type: ignore
    else:
        state["coreg_passed"] = True
        add_trace(state, "coreg_gate", "ok", {"ssim": ssim, "residual": residual}, latency_ms=int((time.time()-t0)*1000))
    return state
