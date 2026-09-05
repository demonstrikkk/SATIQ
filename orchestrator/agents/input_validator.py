"""Agent 1: Input Validator — deterministic, no LLM. Sets deadline_ms + request_key."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import TOTAL_BUDGET_MS, BUDGETS_MS
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency

def _crs_mismatch(assets: list[dict]) -> str | None:
    crs_list = [a.get("crs") for a in assets if a.get("crs")]
    if len(crs_list) <= 1:
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

    # request_key + deadline
    try:
        from orchestrator.core.checkpoint import compute_request_key as _rk
        sar_pol = next((a.get("sar_polarization") for a in assets if isinstance(a, dict) and a.get("sar_polarization")), None)
        plan_pol = (state.get("plan") or {}).get("data_requirements", {}).get("sar_pol") if isinstance(state.get("plan"), dict) else None
        rk = _rk(image_ids or [a.get("asset_id") for a in assets if isinstance(a, dict) and a.get("asset_id")], query, state.get("task_type"), sar_polarization=sar_pol or plan_pol, assets=assets if isinstance(assets, list) else None)
        state["request_key"] = rk
    except Exception:
        state["request_key"] = state.get("request_key") or ""
    _dl = state.get("deadline_ms") or 0
    if not _dl or _dl < 1000000000000:
        state["deadline_ms"] = int(time.time()*1000) + TOTAL_BUDGET_MS
    state.setdefault("checkpoint_hits", [])  # type: ignore
    state.setdefault("node_latencies", {})  # type: ignore
    state.setdefault("retry_policy", {"max_transient": 2, "max_confidence": 3, "max_coreg": 2})  # type: ignore
    state["circuit_breaker_state"] = state.get("circuit_breaker_state") or "closed"
    state["degraded"] = bool(state.get("degraded", False))
    budget = BUDGETS_MS.get("input_validator", 200)

    def _fail(code: str, msg: str, detail: dict | None = None, reason: str | None = None):
        state["error"] = msg
        state["error_type"] = "permanent"
        state["error_code"] = code
        state["validation_passed"] = False
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
        add_trace(state, "input_validator", "failed", detail or {"reason": reason or code}, latency_ms=lat)
        log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"reason": reason or code})
        record_node_latency("input_validator", lat, "permanent")
        return state

    if not query:
        return _fail("empty_query", "query is required", {"reason": "empty query"})
    ql = query.strip()
    ql_norm = " ".join(ql.lower().split())
    has_history = bool(state.get("conversation_history") or state.get("is_followup"))
    has_image = bool(assets or image_ids)
    if len(ql_norm) <= 5 and ql_norm.isalpha() and not has_image and not has_history:
        state["query_intent"] = "greeting"  # type: ignore
        return _fail("greeting", "Hi there! I'm Satiq — your geospatial assistant. Ask me about satellite imagery, like 'detect water bodies in this image' or upload an image to analyze.", {"reason": "greeting_fastpath", "query": query}, "greeting")
    state["query_intent"] = "pending_llm"  # type: ignore
    if len(query) > 4000:
        return _fail("schema_validation_failed", "query exceeds 4000 chars", {"reason": "too_long"})
    if len(query.strip()) < 16 and state.get("query_intent") not in ("greeting",):
        if not (has_image or has_history):
            return _fail("schema_validation_failed", "query too short (minimum 16 characters)", {"reason": "too_short"})
    try:
        from orchestrator.helpers.guardrails import check_prompt_injection
        is_inj, why = check_prompt_injection(query)
        if is_inj:
            return _fail("prompt_injection", f"prompt rejected (injection): {why}", {"reason": "injection", "why": why}, "injection")
    except Exception:
        pass
    mismatch = _crs_mismatch(assets)
    if mismatch:
        s = _fail("crs_mismatch", mismatch, {"reason": mismatch, "assets": assets, "code": "crs_mismatch"}, "crs_mismatch")
        state.setdefault("error_log", []).append(mismatch)  # type: ignore
        return s
    for a in assets:
        gsd = a.get("gsd")
        if gsd is not None and gsd <= 0:
            return _fail("schema_validation_failed", f"invalid GSD {gsd} for asset {a.get('asset_id')}", {"asset": a, "code": "schema_validation_failed"}, "schema_validation_failed")
        try:
            w, h = int(a.get("width") or 0), int(a.get("height") or 0)
            if w and h and w * h > 100_000_000:
                return _fail("image_too_large", f"image too large {w}x{h} (>100Mpix) for asset {a.get('asset_id')}", {"asset": a.get("asset_id"), "w": w, "h": h, "code": "image_too_large"}, "image_too_large")
        except Exception:
            pass
        if a.get("_corrupt") or a.get("corrupt"):
            return _fail("malformed_geotiff", f"malformed GeoTIFF for asset {a.get('asset_id')}", {"asset": a.get("asset_id"), "code": "malformed_geotiff"}, "malformed_geotiff")

    state["validation_passed"] = True
    state["error"] = state["error_type"] = state["error_code"] = None
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
    add_trace(state, "input_validator", "ok", {"query_len": len(query), "num_assets": len(assets), "request_key": state.get("request_key"), "deadline_ms": state.get("deadline_ms")}, latency_ms=lat)
    log_node("input_validator", state.get("request_key",""), "ok", lat, None, {"query_len": len(query)})
    record_node_latency("input_validator", lat)
    return state
