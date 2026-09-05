"""Agent 2: Router — Qwen classification with deterministic pre-analysis + followup."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.llm_client import call_qwen_router
from orchestrator.core.events import emit
from orchestrator.services.query_analyzer import detect_temporal_keywords, detect_spatial_keywords, detect_comparison_keywords
from orchestrator.services.conversation import augment_state_with_history
from orchestrator.core.timeouts import check_deadline_or_raise

async def router_node(state: GraphState) -> GraphState:
    t0 = time.time()
    try:
        check_deadline_or_raise(state.get("deadline_ms", 0), "router")  # type: ignore
    except Exception as e:
        from orchestrator.core.errors import NodeTimeoutError
        if isinstance(e, NodeTimeoutError):
            state["error"] = str(e)
            state["error_type"] = "transient"
            state["error_code"] = "node_timeout"
            state["retry_count"] = state.get("retry_count", 0) + 1
            add_trace(state, "router", "failed", {"error": str(e)}, latency_ms=int((time.time()-t0)*1000))
            return state
        raise
    # followup + conversation history first
    try:
        state = augment_state_with_history(state)  # type: ignore
    except Exception:
        pass
    query = state.get("query","")
    assets = state.get("assets") or []
    # deterministic pre-analysis to feed LLM prompt hints
    try:
        temporal = detect_temporal_keywords(query)
        spatial = detect_spatial_keywords(query)
        comparison = detect_comparison_keywords(query)
        # store for planner
        state["query_analysis"] = {"temporal": temporal, "spatial": spatial, "comparison": comparison}  # type: ignore
        # hint injection: if temporal has change verb but router might misroute grounding, note
        if temporal.get("is_temporal") and "where" in query.lower().split():
            # keep hint for planner to prefer change_vqa with spatial emphasis
            state["temporal_spatial_hint"] = "change_with_spatial"  # type: ignore
    except Exception:
        pass
    # call Qwen off event loop (Groq sync blocks 8s) — free loop for SSE
    import asyncio as _asyncio_router
    result = await _asyncio_router.to_thread(call_qwen_router, query, assets)
    task_type = result.get("task_type","vqa")
    # cross-check task vs input config (orchestrator legality check)
    num_assets = len(assets) or len(state.get("image_ids") or [])
    # if change_vqa but only 1 asset, flag but don't crash — will be handled downstream
    error = None
    if task_type == "change_vqa" and num_assets < 2:
        # keep task but note warning, planner may adjust
        result["warning"] = "change_vqa needs 2 images but only {} provided".format(num_assets)
    if task_type == "optical_sar_fusion" and num_assets < 2:
        result["warning"] = "fusion needs optical+SAR pair but only {} provided".format(num_assets)
    state["task_type"] = task_type  # type: ignore
    state["plan"] = result  # initial plan, planner will refine
    add_trace(state, "router", "ok", {"task_type": task_type, "raw": result}, latency_ms=int((time.time()-t0)*1000))
    # surface the real router decision as a live "thinking" delta in the chat
    sess = state.get("session_id")
    if sess:
        conf = result.get("confidence")
        txt = f"🔀 Router: classified as `{task_type}` (confidence {conf}).\n"
        try:
            await emit(sess, "thinking_delta", {"chunk": txt})
        except Exception:
            pass
    return state
