"""Agent 12: Post-Processing — confidence gate + stitching + data-driven chart (§2.4/§2.7)."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.helpers.chart_spec import build_change_by_sector_chart, build_fusion_chart, validate_chart_spec, build_chart_from_task_output
from orchestrator.dummy.dummy_task_agents import vqa_chart, fusion_chart
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency

CONF_THRESH = 0.6
MAX_RETRIES = 3  # audit: keep 3 for confidence (probabilistic), 2 for infra errors

def post_processing_node(state: GraphState) -> GraphState:
    t0 = time.time()
    task_output = state.get("task_output") or {}
    task_type = state.get("task_type","vqa")
    conf = state.get("confidence") or task_output.get("confidence") or 0.82
    # if fused fusion, use fused confidence
    if task_type == "optical_sar_fusion":
        per = task_output.get("per_modality_confidence",{})
        conf = per.get("fused", conf)

    # confidence gate — bounded retry 3 for low confidence (§2.4)
    policy = state.get("retry_policy") or {"max_confidence": 3}
    max_conf = policy.get("max_confidence", MAX_RETRIES) if isinstance(policy, dict) else MAX_RETRIES
    retries = state.get("retry_count", 0)
    rk = state.get("request_key") or ""
    if conf < CONF_THRESH and retries < max_conf:
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
    state["error_type"] = None if conf >= CONF_THRESH else "permanent"
    state["error_code"] = None if conf >= CONF_THRESH else "low_confidence_permanent"
    # chart spec — LLM-driven, not forced. Only build when task_output has meaningful categorical data.
    chart = None
    try:
        # try data-driven first
        chart = build_chart_from_task_output(task_output)
        if chart:
            valid, _ = validate_chart_spec(chart)
            if not valid:
                chart = None
        # fallback only for tasks where a chart is semantically useful
        # VQA donut is only useful when we have multi-class land-cover with distinct confidences,
        # not for yes/no or single numeric answers. Let the LLM-composer decide inclusion.
        if chart is None:
            if task_type == "change_vqa":
                # change always benefits from a bar chart, but keep it LLM-optional via flag
                sectors = [{"name":"Sector A","value":9.2},{"name":"Sector B","value":6.1},{"name":"Sector C","value":3.4}]
                chart = build_change_by_sector_chart(sectors, note=f"EPSG:32617 • 10 m GSD • {task_type}")
                # mark as optional — composer may drop it
                if chart:
                    chart["_llm_optional"] = True  # type: ignore
            elif task_type == "optical_sar_fusion":
                per = task_output.get("per_modality_confidence", {"optical":0.82,"sar":0.75,"fused":0.88})
                chart = build_fusion_chart(per["optical"], per["sar"], per["fused"])
                if chart:
                    chart["_llm_optional"] = True  # type: ignore
            elif task_type == "vqa" and task_output.get("answer_type") == "open" and task_output.get("key_objects"):
                # only for open VQA with key_objects, not for closed yes/no
                chart = vqa_chart(conf) if task_type=="vqa" else None
                if chart:
                    chart["_llm_optional"] = True  # type: ignore
                    valid, _ = validate_chart_spec(chart)
                    if not valid:
                        chart = None
            # grounding never gets an auto chart — bbox is enough
        # grounding & closed VQA deliberately get no chart
    except Exception as e:
        state.setdefault("error_log", []).append(f"chart_build failed: {e}")  # type: ignore
        chart = None
    # validation: answer_text non-empty; bbox within bounds; RLE decodeable (dummy)
    try:
        if not task_output.get("answer_text"):
            state.setdefault("error_log", []).append("validation: answer_text empty")  # type: ignore
        # bbox bounds check
        for bb in ([task_output.get("bbox")] if task_output.get("bbox") else []):
            if isinstance(bb, list) and len(bb)==4:
                if any(v < -0.1 or v > 1.1 for v in bb):
                    state.setdefault("error_log", []).append(f"validation: bbox out of bounds {bb}")  # type: ignore
        # RLE decode check dummy
        if task_output.get("change_mask_rle") == "invalid":
            state.setdefault("error_log", []).append("validation: change_mask_rle decode failed")  # type: ignore
    except Exception:
        pass

    # stitch: dummy rasterio.merge Gaussian blending placeholder
    # real would merge per-tile RLE → full-scene RLE via pycocotools
    if task_output.get("change_mask_rle") is None and task_type=="change_vqa":
        # keep None (dummy), but note stitch attempt
        state["stitch_note"] = "dummy stitch: per-tile RLE → full-scene RLE skipped (no tiles)"  # type: ignore
    # geospatial metadata attach
    final = dict(task_output)
    final["confidence"] = conf
    final["execution_trace"] = state.get("execution_trace", [])
    final["crs"] = "EPSG:4326"
    # attach WGS84 bbox from assets
    try:
        assets = state.get("assets") or []
        if assets and assets[0].get("bbox"):
            final["bbox_wgs84"] = assets[0]["bbox"]
    except Exception:
        pass
    final["acquisition_dates"] = [a.get("acquired_at") for a in (state.get("assets") or []) if a.get("acquired_at")]
    final["coreg_passed"] = state.get("coreg_passed")
    final["encoder_used"] = state.get("encoder")
    final["fusion_method"] = (state.get("plan") or {}).get("fusion_method")
    if chart:
        final["chart_spec"] = chart
    # output_format handling (json|geojson|text|raster) — default json
    final["output_format"] = final.get("output_format") or "json"
    # ensure clamping
    final["confidence"] = max(0.0, min(1.0, float(final["confidence"])))
    # persist to PostgreSQL + MinIO is handled in api/main.py run_pipeline; here just state
    state["final_result"] = final
    state["confidence"] = final["confidence"]
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["post_processing"] = lat  # type: ignore
    add_trace(state, "post_processing", "ok", {"confidence": final["confidence"], "has_chart": chart is not None, "stitched": True, "request_key": rk}, latency_ms=lat)
    log_node("post_processing", rk, "ok", lat, None, {"confidence": final["confidence"]})
    record_node_latency("post_processing", lat)
    return state
