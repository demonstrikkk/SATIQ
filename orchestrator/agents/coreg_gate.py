"""Agent 7: Co-reg Quality Gate — conditional retry (§2.7 audit #4: transient while retries remain)."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency

def coreg_gate_node(state: GraphState) -> GraphState:
    t0 = time.time()
    rk = state.get("request_key") or ""
    if not state.get("requires_coreg", False):
        state["coreg_passed"] = True
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["coreg_gate"] = lat  # type: ignore
        add_trace(state, "coreg_gate", "skipped", {"reason": "requires_coreg=false bypass", "task_type": state.get("task_type")}, latency_ms=lat)
        log_node("coreg_gate", rk, "skipped", lat, None, {"requires_coreg": False})
        record_node_latency("coreg_gate", lat)
        return state
    coreg = state.get("coreg") or {}
    ssim = coreg.get("ssim", 1.0)
    residual = coreg.get("residual", 0.0)
    passed = coreg.get("passed", True)
    policy = state.get("retry_policy") or {"max_coreg": 2}
    max_coreg = policy.get("max_coreg", 2) if isinstance(policy, dict) else 2
    retries = state.get("coreg_retries", 0)
    if not passed:
        # increment retry counter
        state["coreg_retries"] = retries + 1
        new_retries = state["coreg_retries"]
        # audit #4: transient while retries remain, permanent after max
        if new_retries <= max_coreg:
            state["error_type"] = "transient"
            state["error_code"] = "coreg_retryable"
        else:
            state["error_type"] = "permanent"
            state["error_code"] = "coreg_ssim_below_threshold"
            state["error"] = f"coreg failed after {new_retries} retries (ssim={ssim} residual={residual})"
        state["coreg_passed"] = False
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["coreg_gate"] = lat  # type: ignore
        add_trace(state, "coreg_gate", "failed", {"ssim": ssim, "residual": residual, "retries": new_retries, "error_code": state.get("error_code"), "error_type": state.get("error_type")}, latency_ms=lat)
        log_node("coreg_gate", rk, "failed", lat, state.get("error_type"), {"ssim": ssim, "retries": new_retries})
        record_node_latency("coreg_gate", lat, state.get("error_type"))
        state.setdefault("error_log", []).append(f"coreg failed ssim={ssim} residual={residual} retries={new_retries}")  # type: ignore
    else:
        state["coreg_passed"] = True
        state["error_type"] = None
        state["error_code"] = None
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["coreg_gate"] = lat  # type: ignore
        add_trace(state, "coreg_gate", "ok", {"ssim": ssim, "residual": residual}, latency_ms=lat)
        log_node("coreg_gate", rk, "ok", lat, None, {"ssim": ssim})
        record_node_latency("coreg_gate", lat)
    return state
