"""Agent 13: Error Handler — bounded retry with transient/permanent classification (§2.4)."""
from __future__ import annotations
import asyncio
import json
import time
from datetime import datetime, timezone
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.errors import classify_error_code, classify_exception
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency
from orchestrator.core.dlq import push as dlq_push

# audit fix: keep 3 for confidence, 2 for infra errors — document explicitly
MAX_TRANSIENT_RETRIES = 2
MAX_CONFIDENCE_RETRIES = 3

async def error_handler_node(state: GraphState) -> GraphState:
    t0 = time.time()
    rk = state.get("request_key") or ""
    err = state.get("error") or "unknown error"
    elog = state.get("error_log") or []
    error_code = state.get("error_code")
    error_type = state.get("error_type")
    # classify if not already set
    if not error_type:
        error_type = classify_error_code(error_code or "")
        state["error_type"] = error_type  # type: ignore
    if not error_code:
        error_code = "unknown"
        state["error_code"] = error_code  # type: ignore
    policy = state.get("retry_policy") or {"max_transient": 2, "max_confidence": 3, "max_coreg": 2}
    max_transient = policy.get("max_transient", 2) if isinstance(policy, dict) else 2
    max_conf = policy.get("max_confidence", 3) if isinstance(policy, dict) else 3
    retries = state.get("retry_count", 0)
    coreg_retries = state.get("coreg_retries", 0)
    backoff_ms = 0
    if error_type == "transient":
        if error_code == "coreg_retryable":
            backoff_ms = 0
        elif "confidence" in (error_code or ""):
            if retries < max_conf:
                backoff_ms = 200 * (2 ** retries)
        else:
            if retries < max_transient:
                backoff_ms = 200 * (2 ** retries)
                state["_needs_retry"] = True  # type: ignore
                state["retry_count"] = retries + 1
            else:
                state["_needs_retry"] = False  # type: ignore
    else:
        state["_needs_retry"] = False  # type: ignore
    # Note: real sleep is handled by pipeline retry loop (after_vision/after_fusion) via
    # asyncio.sleep(backoff_ms/1000) there, not here, to keep error_handler fast for tests.
    # The backoff_ms value is used by the caller to sleep before re-entering the node.
    # DLQ emit when permanently failed or transient retries exhausted (except greeting/out_of_scope — not an error)
    is_exhausted = (error_type == "permanent" and error_code not in ("greeting", "out_of_scope")) or (error_type == "transient" and not state.get("_needs_retry"))
    if is_exhausted:
        try:
            dlq_push(state.get("session_id") or rk or "unknown", {
                "request_key": rk,
                "error": err,
                "error_code": error_code,
                "error_type": error_type,
                "task_type": state.get("task_type", "unknown"),
                "retry_count": retries,
                "coreg_retries": coreg_retries,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:
            pass
    # ensure final_result contains structured error
    if not state.get("final_result"):
        # friendly greeting / out_of_scope, not "Unable to complete"
        if error_code in ("greeting", "out_of_scope"):
            state["final_result"] = {
                "task": "chitchat",
                "query": state.get("query",""),
                "answer_text": err,  # err already is friendly greeting / premises message
                "confidence": 1.0,
                "error": None,
                "error_code": error_code,
                "error_type": None,
                "error_log": [],
                "execution_trace": state.get("execution_trace", []),
                "request_key": rk,
                "degraded": False,
                "backoff_ms": 0,
            }
        else:
            state["final_result"] = {
                "task": state.get("task_type","unknown"),
                "query": state.get("query",""),
                "answer_text": f"Unable to complete analysis: {err}",
                "confidence": 0.0,
                "error": err,
                "error_code": error_code,
                "error_type": error_type,
                "error_log": elog,
                "execution_trace": state.get("execution_trace", []),
                "request_key": rk,
                "degraded": state.get("degraded", False),
                "backoff_ms": backoff_ms,
            }
    else:
        # attach error metadata to existing final_result
        try:
            state["final_result"]["error_code"] = error_code  # type: ignore
            state["final_result"]["error_type"] = error_type  # type: ignore
            state["final_result"]["backoff_ms"] = backoff_ms  # type: ignore
        except Exception:
            pass
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["error_handler"] = lat  # type: ignore
    add_trace(state, "error_handler", "ok", {"error": err, "error_code": error_code, "error_type": error_type, "retry_count": retries, "coreg_retries": coreg_retries, "backoff_ms": backoff_ms, "request_key": rk}, latency_ms=lat)
    log_node("error_handler", rk, "ok", lat, error_type, {"code": error_code, "backoff_ms": backoff_ms})
    record_node_latency("error_handler", lat, error_type)
    return state
