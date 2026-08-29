"""Agent 3: Planner — Qwen StepPlan JSON."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.llm_client import call_qwen_planner

def planner_node(state: GraphState) -> GraphState:
    t0 = time.time()
    query = state.get("query","")
    task_type = state.get("task_type","vqa")
    assets = state.get("assets") or []
    plan = call_qwen_planner(query, task_type, assets)
    # enforce task_type consistency
    if plan.get("task_type") != task_type:
        # trust router's task_type as primary, but log divergence
        plan["_router_task"] = task_type
        plan["task_type"] = task_type
    # Full spec fields per cross-verification: steps, tile_config, requires_coreg, etc.
    if "requires_coreg" not in plan:
        plan["requires_coreg"] = task_type in ("change_vqa","optical_sar_fusion")
    if "tile_config" not in plan:
        plan["tile_config"] = {"enabled": True, "size": 256, "overlap_px": 32}
    if "data_requirements" not in plan:
        plan["data_requirements"] = {"temporal": "multi" if task_type in ("change_vqa","optical_sar_fusion") else "single", "bands": ["B2","B3","B4"], "sar_pol": None}
    if "steps" not in plan:
        plan["steps"] = ["preprocessing","vision_encoder","fusion","task_agent"]
    if "fusion_method" not in plan:
        plan["fusion_method"] = "attention" if task_type=="optical_sar_fusion" else "late"
    # spatial decomposition per spec: sub_queries, region_of_interest, spatial_aggregation
    q_low = query.lower()
    # sub_queries: decompose only true multi-part like "Where changed AND how much?" (needs both where/how-much)
    if "sub_queries" not in plan or plan.get("sub_queries") is None:
        sub = None
        has_where = "where" in q_low
        has_how = any(k in q_low for k in ["how much","how many","count","magnitude","area"])
        if " and " in q_low and has_where and has_how:
            import re as _re
            parts = [p.strip() for p in _re.split(r"\s+and\s+", query, flags=_re.IGNORECASE) if p.strip()]
            if len(parts) >= 2 and len(parts[0].split()) >= 2 and len(parts[1].split()) >= 2:
                sub = parts
        plan["sub_queries"] = sub
        state["sub_queries"] = sub  # type: ignore
    # spatial aggregation: "by sector" etc.
    if "spatial_aggregation" not in plan:
        agg = None
        if "by sector" in q_low:
            agg = "by sector"
        elif "by district" in q_low:
            agg = "by district"
        plan["spatial_aggregation"] = agg
        state["spatial_aggregation"] = agg  # type: ignore
    # region geocoding via lightweight gazetteer
    if plan.get("region_of_interest") is None:
        try:
            from orchestrator.services.geocoder import resolve_from_query
            rg = resolve_from_query(query)
            if rg:
                plan["region_of_interest"] = rg
                state["region_of_interest"] = rg  # type: ignore
                # also set requires_coreg already
        except Exception:
            pass
    # mirror to state for coreg bypass
    state["requires_coreg"] = bool(plan["requires_coreg"])
    state["plan"] = plan
    add_trace(state, "planner", "ok", {"plan": plan, "requires_coreg": state["requires_coreg"], "sub_queries": plan.get("sub_queries"), "region": plan.get("region_of_interest")}, latency_ms=int((time.time()-t0)*1000))
    return state
