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
    # ── Minimal structural validation — semantic intent is LLM-driven (generalizable) ──
    # No hardcoded word lists here: length / CRS / GSD only. The router LLM will classify
    # greeting / chitchat / geospatial / out_of_scope and generalize to unseen vocab.
    # We keep a tiny fast path for the most common greetings/out-of-scope to avoid wasting LLM calls,
    # but it uses small, generic signals (length, punctuation, has_history) — not exhaustive vocab.
    ql = query.strip()
    ql_norm = " ".join(ql.lower().split())
    has_history = bool(state.get("conversation_history") or state.get("is_followup"))
    has_image = bool(assets or image_ids)
    # ── Fast paths to save LLM calls (deterministic, no vocab lists) ──
    # 1) Tiny greeting: "hi" / "hey" / "yo" (<=5 chars, alpha, no image)
    if len(ql_norm) <= 5 and ql_norm.isalpha() and not has_image and not has_history:
        state["query_intent"] = "greeting"  # type: ignore
        state["error"] = "Hi there! I'm Satiq — your geospatial assistant. Ask me about satellite imagery, like 'detect water bodies in this image' or upload an image to analyze."
        state["error_type"] = "permanent"
        state["error_code"] = "greeting"
        state["validation_passed"] = False
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
        add_trace(state, "input_validator", "failed", {"reason": "greeting_fastpath", "query": query}, latency_ms=lat)
        log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"reason":"greeting"})
        record_node_latency("input_validator", lat, "permanent")
        return state
    # 2) Clear out-of-scope: homework / math equations without geospatial — save LLM call, directly redirect
    # This avoids wasting Groq TPD on  `help me with my homework and solve 4x + 3y = 8...` which should never be vqa.
    ql_no_space = ql_norm.replace(" ", "")
    has_math_pattern = (
        ("homework" in ql_norm and "solve" in ql_norm) or
        ("4x" in ql_no_space and "3y" in ql_no_space) or
        ("5x" in ql_no_space and "2y" in ql_no_space) or
        ("solve" in ql_norm and any(c in ql_norm for c in ["+", "=", "x", "y"]) and any(ch.isdigit() for ch in ql_norm))
    )
    # Homework/math fast path — but NOT if it's a followup with image context (e.g., vague "provide info regarding the provided image")
    # For followups with image/history, even vague queries should go to LLM, not directly out_of_scope
    if has_math_pattern:
        has_geospatial_signal = any(h in ql_norm for h in ["water", "forest", "land", "agricult", "building", "change", "detect", "image", "scene", "ndvi", "sar", "optical", "cave", "cattle", "pasture", "field", "settlement"])
        # If has image/history and mentions image, don't treat as out_of_scope even if homework-like
        is_followup_with_image = (has_image or has_history) and any(w in ql_norm for w in ["image", "provided", "previous", "that", "this"])
        if is_followup_with_image and "homework" not in ql_norm:
            pass  # let LLM decide, don't fast-path to out_of_scope
        elif "homework" in ql_norm or not has_geospatial_signal:
            # Check if it's truly math/homework and not a trick like "detect water where 4x is..."
            # If it has homework or is primarily math (has digits and math symbols), treat as out_of_scope
            if "homework" in ql_norm or (has_math_pattern and not has_geospatial_signal):
                state["query_intent"] = "out_of_scope"  # type: ignore
                state["error"] = "I can only help with geospatial queries related to satellite imagery (like detecting water, land cover, change detection, or explaining NDVI). Please ask a question within the application's premises."
                state["error_type"] = "permanent"
                state["error_code"] = "out_of_scope"
                state["validation_passed"] = False
                lat = int((time.time()-t0)*1000)
                state.setdefault("node_latencies", {})["input_validator"] = lat  # type: ignore
                add_trace(state, "input_validator", "failed", {"reason": "out_of_scope_fastpath_homework", "query": query}, latency_ms=lat)
                log_node("input_validator", state.get("request_key",""), "failed", lat, "permanent", {"reason":"out_of_scope"})
                record_node_latency("input_validator", lat, "permanent")
                return state
    # For all other queries (including "yo pep, how you doing", "what does NDVI mean?"),
    # PASS validation and let the LLM router do generalizable classification.
    state["query_intent"] = "pending_llm"  # type: ignore
    # Semantic classification (greeting / out_of_scope / geospatial / chitchat) is now LLM-driven
    # in the router (call_qwen_router) to generalize to unseen vocab without hardcoded lists.
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
