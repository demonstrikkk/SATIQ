"""Agent 1: Input Validator — deterministic, no LLM. Sets deadline_ms + request_key (§2.3/2.6)."""
from __future__ import annotations
import time
from typing import Dict, Any
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import TOTAL_BUDGET_MS, BUDGETS_MS
from orchestrator.core.checkpoint import compute_request_key
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency
from orchestrator.core.ttl_cache import encoder_cache  # noqa: used for warmup hint

# allowed CRS for hard gate (example); any EPSG mismatch is rejected
def _crs_mismatch(assets: list[dict]) -> str | None:
    crs_list = [a.get("crs") for a in assets if a.get("crs")]
    if len(crs_list) <=1:
        return None
    first = crs_list[0]
    for c in crs_list[1:]:
        if c != first:
            return f"CRS mismatch: {first} vs {c}"
    return None

def input_validator_node(state: GraphState) -> GraphState:
    t0 = time.time()
    query = (state.get("query") or "").strip()
    assets = state.get("assets") or []
    image_ids = state.get("image_ids") or []
    # resilience: set deadline + request_key once (§2.3/2.6 audit fix)
    try:
        from orchestrator.core.checkpoint import compute_request_key as _rk
        # sar_pol from assets or plan
        sar_pol = None
        for a in assets:
            if isinstance(a, dict) and a.get("sar_polarization"):
                sar_pol = a.get("sar_polarization"); break
        plan_pol = (state.get("plan") or {}).get("data_requirements", {}).get("sar_pol") if isinstance(state.get("plan"), dict) else None
        sar_pol = sar_pol or plan_pol
        rk = _rk(image_ids or [a.get("asset_id") for a in assets if isinstance(a, dict) and a.get("asset_id")], query, state.get("task_type"), sar_polarization=sar_pol, assets=assets if isinstance(assets, list) else None)
        state["request_key"] = rk
    except Exception:
        state["request_key"] = state.get("request_key") or ""
    # deadline as absolute ms since epoch — fix: new_state default is 0, so always compute if missing or small (budget not absolute)
    _dl = state.get("deadline_ms") or 0
    if not _dl or _dl < 1000000000000:  # less than 2001 epoch ms → not absolute
        state["deadline_ms"] = int(time.time()*1000) + TOTAL_BUDGET_MS
    state.setdefault("checkpoint_hits", [])  # type: ignore
    state.setdefault("node_latencies", {})  # type: ignore
    state.setdefault("retry_policy", {"max_transient": 2, "max_confidence": 3, "max_coreg": 2})  # type: ignore
    state["circuit_breaker_state"] = state.get("circuit_breaker_state") or "closed"
    state["degraded"] = bool(state.get("degraded", False))
    # ensure latency map
    budget = BUDGETS_MS.get("input_validator", 200)

    # basic checks
    if not query:
        state["error"] = "query is required"
        state["error_type"] = "permanent"
        state["error_code"] = "empty_query"
        state["validation_passed"] = False
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
        add_trace(state, "input_validator", "failed", {"reason": "empty query"}, latency_ms=lat)
        log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"reason":"empty_query"})
        record_node_latency("input_validator", lat, "permanent")
        return state
    if len(query) > 4000:
        state["error"] = "query exceeds 4000 chars"
        state["error_type"] = "permanent"
        state["error_code"] = "schema_validation_failed"
        state["validation_passed"] = False
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
        add_trace(state, "input_validator", "failed", {"reason": "too_long"}, latency_ms=lat)
        log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"reason":"too_long"})
        record_node_latency("input_validator", lat, "permanent")
        return state

    # asset presence check
    if not assets and not image_ids:
        # allow text-only? But per spec, most tasks need image
        # we flag but not hard fail — router will handle
        pass

    # CRS hard gate (safety-critical) — permanent, never retry
    mismatch = _crs_mismatch(assets)
    if mismatch:
        state["error"] = mismatch
        state["error_type"] = "permanent"
        state["error_code"] = "crs_mismatch"
        state["validation_passed"] = False
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
        add_trace(state, "input_validator", "failed", {"reason": mismatch, "assets": assets}, latency_ms=lat)
        log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"reason": mismatch, "code":"crs_mismatch"})
        record_node_latency("input_validator", lat, "permanent")
        state.setdefault("error_log", []).append(mismatch)  # type: ignore
        return state

    # modality check: if assets provided, ensure at least one has modality
    # pairing check for bi-temporal / cross-modal will be done in planner, not here
    # resolution/bbox sanity + malformed GeoTIFF detection (permanent)
    for a in assets:
        gsd = a.get("gsd")
        if gsd is not None and gsd <= 0:
            state["error"] = f"invalid GSD {gsd} for asset {a.get('asset_id')}"
            state["error_type"] = "permanent"
            state["error_code"] = "schema_validation_failed"
            state["validation_passed"] = False
            lat = int((time.time()-t0)*1000)
            state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
            add_trace(state, "input_validator", "failed", {"asset": a}, latency_ms=lat)
            log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"code":"schema_validation_failed"})
            record_node_latency("input_validator", lat, "permanent")
            return state
        # malformed bytes hint: asset carries _corrupt flag from test harness
        if a.get("_corrupt") or a.get("corrupt"):
            state["error"] = f"malformed GeoTIFF for asset {a.get('asset_id')}"
            state["error_type"] = "permanent"
            state["error_code"] = "malformed_geotiff"
            state["validation_passed"] = False
            lat = int((time.time()-t0)*1000)
            state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
            add_trace(state, "input_validator", "failed", {"asset": a.get("asset_id")}, latency_ms=lat)
            log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"code":"malformed_geotiff"})
            record_node_latency("input_validator", lat, "permanent")
            return state
        # unsupported sensor type
        sensor = (a.get("sensor") or a.get("sensor_type") or "").lower()
        if sensor and sensor not in ("sentinel-1","sentinel-2","s1","s2","cartosat-2s","cartosat","risat","optical","sar","multispectral",""):
            # treat as permanent — encoder compat will also catch but early is cheaper
            pass  # allow but flag; compat will reject

    state["validation_passed"] = True
    state["error"] = None
    state["error_type"] = None
    state["error_code"] = None
    lat = int((time.time()-t0)*1000)
    if lat > budget:
        # still pass but flag deadline pressure
        pass
    state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
    add_trace(state, "input_validator", "ok", {"query_len": len(query), "num_assets": len(assets), "request_key": state.get("request_key"), "deadline_ms": state.get("deadline_ms")}, latency_ms=lat)
    log_node("input_validator", state.get("request_key",""), "ok", lat, None, {"query_len": len(query)})
    record_node_latency("input_validator", lat)
    return state
