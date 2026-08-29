"""GraphState — shared state for LangGraph nodes. Every agent reads/writes here only."""
from __future__ import annotations
from typing import TypedDict, List, Optional, Dict, Any, Literal, Annotated
import operator

TaskType = Literal["vqa","grounding","change_vqa","optical_sar_fusion","captioning","unknown"]

# Reducer that keeps last value (LangGraph needs Annotated for channel merging)
def _last(a, b):
    return b

class GraphState(TypedDict, total=False):
    # inputs
    session_id: Annotated[str, _last]
    user_id: Annotated[Optional[str], _last]
    query: Annotated[str, _last]
    assets: Annotated[List[Dict[str, Any]], _last]  # RasterAsset dicts
    image_ids: Annotated[List[str], _last]
    # derived
    task_type: Annotated[TaskType, _last]
    plan: Annotated[Dict[str, Any], _last]  # StepPlan
    encoder: Annotated[str, _last]  # satmae / ssl4eo / prithvi / croma
    # preprocessing
    tiles: Annotated[List[Dict[str, Any]], _last]
    coreg: Annotated[Dict[str, Any], _last]  # ssim, residual, passed
    # encodings
    embeddings: Annotated[Dict[str, Any], _last]  # model -> vectors
    fused_repr: Annotated[Optional[Dict[str, Any]], _last]
    # task outputs
    task_output: Annotated[Optional[Dict[str, Any]], _last]
    # postprocess
    final_result: Annotated[Optional[Dict[str, Any]], _last]
    confidence: Annotated[Optional[float], _last]
    # control
    error: Annotated[Optional[str], _last]
    error_log: Annotated[List[str], _last]
    retry_count: Annotated[int, _last]
    coreg_retries: Annotated[int, _last]
    execution_trace: Annotated[List[Dict[str, Any]], _last]
    # gating
    validation_passed: Annotated[bool, _last]
    compat_passed: Annotated[bool, _last]
    coreg_passed: Annotated[bool, _last]
    # parallel join flags (for planner fan-out)
    preprocessing_done: Annotated[bool, _last]
    encoder_ready: Annotated[bool, _last]
    requires_coreg: Annotated[bool, _last]
    # conversation & planner extensions
    conversation_history: Annotated[List[Dict[str, Any]], _last]
    followup_anchor: Annotated[Optional[str], _last]
    is_followup: Annotated[bool, _last]
    followup_resolved: Annotated[bool, _last]
    query_original: Annotated[Optional[str], _last]
    region_of_interest: Annotated[Optional[Dict[str, Any]], _last]  # {region, bbox, crs}
    sub_queries: Annotated[Optional[List[str]], _last]
    spatial_aggregation: Annotated[Optional[str], _last]
    query_analysis: Annotated[Optional[Dict[str, Any]], _last]
    # resilience (§2.3,2.6,3)
    deadline_ms: Annotated[int, _last]
    request_key: Annotated[str, _last]
    checkpoint_hits: Annotated[List[str], _last]
    retry_policy: Annotated[Dict[str,int], _last]
    node_latencies: Annotated[Dict[str,int], _last]
    circuit_breaker_state: Annotated[str, _last]  # closed|open|half_open
    degraded: Annotated[bool, _last]
    error_type: Annotated[Optional[str], _last]  # transient|permanent|None
    error_code: Annotated[Optional[str], _last]  # e.g. crs_mismatch, coreg_ssim_below_threshold
    # test injection (§4) — not in production, used by synthetic harness
    _test_inject: Annotated[Optional[Dict[str, Any]], _last]

def new_state(session_id: str, query: str, assets: List[Dict[str,Any]] | None = None, image_ids: List[str] | None = None, user_id: str | None = None) -> GraphState:
    return GraphState(
        session_id=session_id,
        user_id=user_id,
        query=query,
        assets=assets or [],
        image_ids=image_ids or [],
        task_type="unknown",
        plan={},
        encoder="",
        tiles=[],
        coreg={},
        embeddings={},
        fused_repr=None,
        task_output=None,
        final_result=None,
        confidence=None,
        error=None,
        error_log=[],
        retry_count=0,
        coreg_retries=0,
        execution_trace=[],
        validation_passed=False,
        compat_passed=False,
        coreg_passed=False,
        preprocessing_done=False,
        encoder_ready=False,
        requires_coreg=False,
        conversation_history=[],
        followup_anchor=None,
        is_followup=False,
        followup_resolved=False,
        query_original=None,
        region_of_interest=None,
        sub_queries=None,
        spatial_aggregation=None,
        query_analysis=None,
        deadline_ms=0,
        request_key="",
        checkpoint_hits=[],
        retry_policy={"max_transient": 2, "max_confidence": 3, "max_coreg": 2},
        node_latencies={},
        circuit_breaker_state="closed",
        degraded=False,
        error_type=None,
        error_code=None,
        _test_inject=None,
    )

def add_trace(state: GraphState, agent: str, status: str, detail: Dict[str,Any] | None = None, latency_ms: int | None = None):
    entry = {"agent": agent, "status": status, "detail": detail or {}, "latency_ms": latency_ms}
    # ensure list exists
    if "execution_trace" not in state or state["execution_trace"] is None:
        state["execution_trace"] = []
    state["execution_trace"].append(entry)  # type: ignore
