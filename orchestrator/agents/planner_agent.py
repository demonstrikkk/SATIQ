"""Agent 3: Planner — Qwen StepPlan JSON."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.llm_client import call_qwen_planner
from orchestrator.core.events import emit
from orchestrator.core.timeouts import check_deadline_or_raise

async def planner_node(state: GraphState) -> GraphState:
    t0 = time.time()
    try:
        check_deadline_or_raise(state.get("deadline_ms", 0), "planner")  # type: ignore
    except Exception as e:
        from orchestrator.core.errors import NodeTimeoutError
        if isinstance(e, NodeTimeoutError):
            state["error"] = str(e)
            state["error_type"] = "transient"
            state["error_code"] = "node_timeout"
            state["retry_count"] = state.get("retry_count", 0) + 1
            add_trace(state, "planner", "failed", {"error": str(e)}, latency_ms=int((time.time()-t0)*1000))
            return state
        raise
    query = state.get("query","")
    task_type = state.get("task_type","vqa")
    assets = state.get("assets") or []
    query_intent = state.get("query_intent") or "geospatial"  # type: ignore
    # Also consider router's task_type as intent — LLM router now returns greeting/chitchat/help/out_of_scope directly
    router_intent = task_type if task_type in ("greeting","chitchat","help","out_of_scope","pending_llm") else None
    if router_intent:
        query_intent = router_intent  # type: ignore
    skip_hint = state.get("skip_models_hint") or False  # type: ignore
    # ── fast path: general text / help / chitchat / greeting / out_of_scope without image → skip heavy vision ──
    ql = query.lower()
    has_geospatial_need = any(h in ql for h in ["detect", "find", "locate", "where", "how many", "count", "is there", "compare", "sar", "optical", "image", "scene", "bbox", "water", "forest", "building", "urban", "agricult", "crop", "field", "change", "cave", "cattle", "pasture"])
    is_definitional = any(p in ql for p in ["what is", "what does", "what are", "define", "meaning of", "explain"])
    has_detection_verb = any(v in ql for v in ["detect", "find", "locate", "where is", "how many", "count", "is there", "compare", "show me", "identify"])
    definitional_skip = is_definitional and not has_detection_verb and not assets and not state.get("is_followup")
    # Unified skip: any non-geospatial intent should skip vision
    is_non_geospatial = query_intent in ("greeting","chitchat","help","out_of_scope","pending_llm") or task_type in ("greeting","chitchat","help","out_of_scope")
    # For out_of_scope/greeting, always skip; for chitchat/help, skip if no geospatial need
    if query_intent in ("greeting","out_of_scope") or task_type in ("greeting","out_of_scope"):
        # will be handled as friendly redirection, skip models
        plan = {
            "task_type": query_intent if query_intent in ("greeting","out_of_scope") else task_type,
            "reasoning": f"Router classified as {query_intent or task_type} — outside geospatial premises, will redirect",
            "required_assets": [],
            "fusion_needed": False,
            "temporal_needed": False,
            "confidence": 0.95,
            "skip_models": True,
            "requires_coreg": False,
            "tile_config": {"enabled": False, "size": 256, "overlap_px": 0},
            "data_requirements": {"temporal": "single", "bands": [], "sar_pol": None},
            "steps": ["response_composer"],
            "fusion_method": "none",
        }
        state["plan"] = plan  # type: ignore
        state["task_type"] = plan["task_type"]  # type: ignore
        state["requires_coreg"] = False  # type: ignore
        state["skip_models"] = True  # type: ignore
        add_trace(state, "planner", "ok", {"plan": plan, "skip_models": True, "query_intent": query_intent, "router_task": task_type}, latency_ms=int((time.time()-t0)*1000))
        sess = state.get("session_id")
        if sess:
            try:
                await emit(sess, "thinking_delta", {"chunk": f"🧭 Planner: {query_intent} — outside premises, will redirect\n"})
            except Exception:
                pass
        return state
    if ((query_intent in ("chitchat", "help") or skip_hint or definitional_skip or is_non_geospatial) and not has_geospatial_need and not assets) or definitional_skip:
        # also check if it's a followup that needs previous image context — if has_history, still skip unless it references spatial
        if not state.get("is_followup") or not any(h in ql for h in ["that", "previous", "same area", "same region"]):
            plan = {
                "task_type": "chitchat",
                "reasoning": f"Query is {query_intent} general text without requiring vision models — will answer directly via composer",
                "required_assets": [],
                "fusion_needed": False,
                "temporal_needed": False,
                "confidence": 0.95,
                "skip_models": True,
                "requires_coreg": False,
                "tile_config": {"enabled": False, "size": 256, "overlap_px": 0},
                "data_requirements": {"temporal": "single", "bands": [], "sar_pol": None},
                "steps": ["response_composer"],
                "fusion_method": "none",
            }
            state["plan"] = plan  # type: ignore
            state["task_type"] = "chitchat"  # type: ignore
            state["requires_coreg"] = False  # type: ignore
            state["skip_models"] = True  # type: ignore
            add_trace(state, "planner", "ok", {"plan": plan, "skip_models": True, "query_intent": query_intent}, latency_ms=int((time.time()-t0)*1000))
            sess = state.get("session_id")
            if sess:
                try:
                    await emit(sess, "thinking_delta", {"chunk": f"🧭 Planner: {query_intent} — skipping vision, direct text response\n"})
                except Exception:
                    pass
            return state
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
    # surface the real planner reasoning as a live "thinking" delta in the chat
    sess = state.get("session_id")
    if sess:
        reasoning = (plan.get("reasoning") or "").strip()
        txt = f"🧭 Planner ({plan.get('_provider','qwen')}): {reasoning}\n" if reasoning else f"🧭 Planner ({plan.get('_provider','qwen')}): task={plan.get('task_type')}, coreg={plan.get('requires_coreg')}\n"
        try:
            await emit(sess, "thinking_delta", {"chunk": txt})
        except Exception:
            pass
    return state
