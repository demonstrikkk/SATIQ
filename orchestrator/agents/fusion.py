"""Agent 9: Multimodal Fusion — service boundary + deadline + circuit breaker (§2.1/2.3/2.5)."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import BUDGETS_MS, check_deadline_or_raise
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency
from orchestrator.core.errors import NodeTimeoutError, CircuitOpenError
from orchestrator.dummy.dummy_fusion import run_fusion
try:
    from orchestrator.services.fusion_llm_service import fuse as service_fuse
except Exception:
    service_fuse = None  # type: ignore

def fusion_node(state: GraphState) -> GraphState:
    t0 = time.time()
    rk = state.get("request_key") or ""
    try:
        check_deadline_or_raise(state.get("deadline_ms", 0), "fusion")
    except NodeTimeoutError as e:
        lat = int((time.time()-t0)*1000)
        state["error"] = str(e); state["error_type"]="transient"; state["error_code"]="node_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
        add_trace(state, "fusion", "failed", {"error": str(e), "retry": state["retry_count"]}, latency_ms=lat)
        log_node("fusion", rk, "failed", lat, "transient", {"timeout": True, "retry": state["retry_count"]})
        record_node_latency("fusion", lat, "transient")
        return state
    _inj = state.get("_test_inject") or {}
    if isinstance(_inj, dict) and _inj.get("fusion_slow"):
        e = NodeTimeoutError("fusion", budget_ms=BUDGETS_MS.get("fusion",6000), elapsed_ms=6001)
        lat = int((time.time()-t0)*1000)
        state["error"] = str(e); state["error_type"]="transient"; state["error_code"]="fusion_llm_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
        add_trace(state, "fusion", "failed", {"error": "injected slow", "retry": state["retry_count"]}, latency_ms=lat)
        log_node("fusion", rk, "failed", lat, "transient", {"injected": True, "retry": state["retry_count"]})
        record_node_latency("fusion", lat, "transient")
        return state
    if isinstance(_inj, dict) and _inj.get("fusion_flaky") and state.get("retry_count",0)==0:
        lat = int((time.time()-t0)*1000)
        state["error"] = "flaky fusion (injected)"
        state["error_type"]="transient"; state["error_code"]="fusion_llm_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
        add_trace(state, "fusion", "failed", {"error": "flaky", "retry": state["retry_count"]}, latency_ms=lat)
        log_node("fusion", rk, "failed", lat, "transient", {"flaky": True, "retry": state["retry_count"]})
        record_node_latency("fusion", lat, "transient")
        return state
    raw = state.get("_embeddings_raw") or state.get("embeddings") or {}
    if isinstance(raw, dict) and any(isinstance(v, dict) and "_raw" in v for v in raw.values()):
        raw = state.get("_embeddings_raw", raw)
    query = state.get("query","")
    method = "attention"
    if state.get("task_type") == "optical_sar_fusion":
        method = "attention"
    elif state.get("encoder") == "croma":
        method = "attention"
    budget_ms = BUDGETS_MS.get("fusion", 6000)
    fused = None
    try:
        if service_fuse is not None:
            fused = service_fuse(raw, timeout_ms=budget_ms, query=query)
        else:
            fused = run_fusion(raw, query, method=method)
    except CircuitOpenError as ce:
        lat = int((time.time()-t0)*1000)
        # degraded: return mock fused repr with degraded flag instead of hanging
        state["error"] = str(ce); state["error_type"]="transient"; state["error_code"]="circuit_open"
        state["degraded"] = True
        # produce degraded fused repr so downstream can still answer
        try:
            fused = run_fusion(raw, query, method=method)
            fused["degraded"] = True
            fused["degraded_reason"] = "circuit_open fallback"
            state["fused_repr"] = fused
            state["error"] = None; state["error_type"]=None; state["error_code"]=None
            lat2 = int((time.time()-t0)*1000)
            state.setdefault("node_latencies", {})["fusion"] = lat2  # type: ignore
            add_trace(state, "fusion", "ok_degraded", {"method": method, "circuit": True}, latency_ms=lat2)
            log_node("fusion", rk, "ok_degraded", lat2, "transient", {"circuit": True})
            record_node_latency("fusion", lat2, "transient")
            return state
        except Exception:
            state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
            add_trace(state, "fusion", "failed", {"error": "circuit_open"}, latency_ms=lat)
            log_node("fusion", rk, "failed", lat, "transient", {"circuit": True})
            record_node_latency("fusion", lat, "transient")
            return state
    except NodeTimeoutError as e:
        lat = int((time.time()-t0)*1000)
        state["error"] = str(e); state["error_type"]="transient"; state["error_code"]="fusion_llm_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
        add_trace(state, "fusion", "failed", {"error": str(e), "retry": state["retry_count"]}, latency_ms=lat)
        log_node("fusion", rk, "failed", lat, "transient", {"timeout": True, "retry": state["retry_count"]})
        record_node_latency("fusion", lat, "transient")
        return state
    except Exception as e:
        lat = int((time.time()-t0)*1000)
        state["error"] = str(e)[:200]; state["error_type"]="transient"; state["error_code"]="fusion_llm_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
        add_trace(state, "fusion", "failed", {"error": str(e)[:120], "retry": state["retry_count"]}, latency_ms=lat)
        log_node("fusion", rk, "failed", lat, "transient", {"exc": str(e)[:80], "retry": state["retry_count"]})
        record_node_latency("fusion", lat, "transient")
        return state
    if fused is None:
        try:
            fused = run_fusion(raw, query, method=method)
        except Exception as e:
            lat = int((time.time()-t0)*1000)
            state["error"]=str(e); state["error_type"]="transient"; state["error_code"]="fusion_llm_timeout"
            state["retry_count"] = state.get("retry_count",0) + 1
            state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
            add_trace(state, "fusion", "failed", {"error": str(e)[:120], "retry": state["retry_count"]}, latency_ms=lat)
            log_node("fusion", rk, "failed", lat, "transient", {"exc": str(e)[:80], "retry": state["retry_count"]})
            record_node_latency("fusion", lat, "transient")
            return state
    state["error"] = None; state["error_type"] = None; state["error_code"] = None
    state["fused_repr"] = fused
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["fusion"] = lat  # type: ignore
    add_trace(state, "fusion", "ok", {"method": method, "confidence": fused.get("confidence") if isinstance(fused, dict) else None, "dim": fused.get("dim") if isinstance(fused, dict) else None, "request_key": rk}, latency_ms=lat)
    log_node("fusion", rk, "ok", lat, None, {"method": method})
    record_node_latency("fusion", lat)
    return state
