"""Agent 13: Error Handler — logs and formats error response."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace

def error_handler_node(state: GraphState) -> GraphState:
    t0 = time.time()
    err = state.get("error") or "unknown error"
    elog = state.get("error_log") or []
    # ensure final_result contains error
    if not state.get("final_result"):
        state["final_result"] = {
            "task": state.get("task_type","unknown"),
            "query": state.get("query",""),
            "answer_text": f"Unable to complete analysis: {err}",
            "confidence": 0.0,
            "error": err,
            "error_log": elog,
            "execution_trace": state.get("execution_trace", []),
        }
    add_trace(state, "error_handler", "ok", {"error": err}, latency_ms=int((time.time()-t0)*1000))
    return state
