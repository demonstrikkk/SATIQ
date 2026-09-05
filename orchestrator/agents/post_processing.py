"""Agent 12: Post-Processing — confidence gate + real chart only."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.helpers.chart_spec import validate_chart_spec, build_chart_from_task_output
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency

CONF_THRESH = 0.6
MAX_RETRIES = 2  # ADR 0009 reflection cap — single source is pipeline.MAX_REFLECTION_ITERATIONS

def post_processing_node(state: GraphState) -> GraphState:
    t0 = time.time()
    task_output = state.get("task_output") or {}
    task_type = state.get("task_type","vqa")
    # Never invent confidence — use real value only (None stays None, gate will treat as pass for now)
    conf = state.get("confidence")
    if conf is None:
        conf = task_output.get("confidence")
    # if fused fusion, use fused confidence if present
    if task_type == "optical_sar_fusion":
        per = task_output.get("per_modality_confidence",{})
        fused = per.get("fused")
        if fused is not None:
            conf = fused

    # confidence gate — only if real confidence present, else no retry
    policy = state.get("retry_policy") or {"max_confidence": 3}
    max_conf = policy.get("max_confidence", MAX_RETRIES) if isinstance(policy, dict) else MAX_RETRIES
    retries = state.get("retry_count", 0)
    rk = state.get("request_key") or ""
    # If confidence is None (model has no score, e.g., GeoChat), do not invented-gate — pass through
    if conf is not None and conf < CONF_THRESH and retries < max_conf:
        state["retry_count"] = retries + 1
        state["error_type"] = "transient"
        state["error_code"] = "low_confidence"
        lat = int((time.time()-t0)*1000)
        state.setdefault("node_latencies", {})["post_processing"] = lat  # type: ignore
        add_trace(state, "post_processing", "retry", {"confidence": conf, "threshold": CONF_THRESH, "retry": retries+1, "max_confidence": max_conf}, latency_ms=lat)
        log_node("post_processing", rk, "retry", lat, "transient", {"confidence": conf, "retry": retries+1})
        record_node_latency("post_processing", lat, "transient")
        state["_needs_retry"] = True  # type: ignore
        return state

    state["_needs_retry"] = False  # type: ignore
    state["error_type"] = None if (conf is None or conf >= CONF_THRESH) else "permanent"
    state["error_code"] = None if (conf is None or conf >= CONF_THRESH) else "low_confidence_permanent"
    # chart spec — only real data-driven
    chart = None
    try:
        chart = build_chart_from_task_output(task_output)
        if chart:
            valid, _ = validate_chart_spec(chart)
            if not valid:
                chart = None
        # No fallback — if no real categorical data, no chart
    except Exception as e:
        state.setdefault("error_log", []).append(f"chart_build failed: {e}")  # type: ignore
        chart = None
    # validation: answer_text non-empty; bbox clamp to [0,1]; RLE
    try:
        if not task_output.get("answer_text"):
            state.setdefault("error_log", []).append("validation: answer_text empty")  # type: ignore
        # bbox clamp to valid [0,1] — real model should already be normalized, but enforce
        for key in ("bbox", "bbox_normalized"):
            bb = task_output.get(key)
            if isinstance(bb, list) and len(bb)==4:
                clamped = [max(0.0, min(1.0, float(v))) for v in bb]
                if clamped != bb:
                    task_output[key] = clamped  # mutate to valid
                    state.setdefault("error_log", []).append(f"bbox clamped {bb} -> {clamped}")  # type: ignore
                if any(v < -0.1 or v > 1.1 for v in bb):
                    state.setdefault("error_log", []).append(f"validation: bbox out of bounds {bb}")  # type: ignore
        if task_output.get("change_mask_rle") == "invalid":
            state.setdefault("error_log", []).append("validation: change_mask_rle decode failed")  # type: ignore
        # evidence grounding verification: final text must reflect bbox/categories if grounding/change
        ans = (task_output.get("answer_text") or "").lower()
        if task_type == "grounding" and task_output.get("bbox_xyxy") and "bbox" not in ans and "box" not in ans:
            state.setdefault("error_log", []).append("evidence grounding: grounding bbox present but answer_text missing bbox mention")  # type: ignore
        if task_type == "change_vqa" and task_output.get("change_categories") and not any(c.lower() in ans for c in task_output["change_categories"]):
            state.setdefault("error_log", []).append("evidence grounding: change categories not cited in answer")  # type: ignore
        # structured output enforcement: check markdown tables have valid pipe structure if present
        if "|" in ans and ans.count("|") % 2 != 0:
            state.setdefault("error_log", []).append("structured output: malformed table pipes")  # type: ignore
    except Exception:
        pass

    # geospatial metadata attach — use real asset CRS/bbox
    final = dict(task_output)
    if conf is not None:
        final["confidence"] = max(0.0, min(1.0, float(conf)))
    else:
        final.pop("confidence", None)
    final["execution_trace"] = state.get("execution_trace", [])
    # CRS is whatever asset reported, not invented EPSG:4326
    try:
        assets = state.get("assets") or []
        if assets and assets[0].get("crs"):
            final["crs"] = assets[0]["crs"]
    except Exception:
        pass
    final["acquisition_dates"] = [a.get("acquired_at") for a in (state.get("assets") or []) if a.get("acquired_at")]
    if chart:
        final["chart_spec"] = chart
    final["output_format"] = final.get("output_format") or "json"
    # persist to PostgreSQL + MinIO is handled in api/main.py run_pipeline; here just state
    state["final_result"] = final
    state["confidence"] = final.get("confidence")
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["post_processing"] = lat  # type: ignore
    add_trace(state, "post_processing", "ok", {"confidence": final["confidence"], "has_chart": chart is not None, "stitched": True, "request_key": rk}, latency_ms=lat)
    log_node("post_processing", rk, "ok", lat, None, {"confidence": final["confidence"]})
    record_node_latency("post_processing", lat)
    return state
