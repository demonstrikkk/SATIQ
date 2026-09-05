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
    # task outputs
    task_output: Annotated[Optional[Dict[str, Any]], _last]
    # postprocess
    final_result: Annotated[Optional[Dict[str, Any]], _last]
    confidence: Annotated[Optional[float], _last]
    # control
    error: Annotated[Optional[str], _last]
    error_log: Annotated[List[str], _last]
    retry_count: Annotated[int, _last]
    execution_trace: Annotated[List[Dict[str, Any]], _last]
    # gating
    validation_passed: Annotated[bool, _last]
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
    # resilience — deadline_at authoritative, remaining derived (P0-03)
    deadline_ms: Annotated[int, _last]  # alias for deadline_at (ms epoch) — authoritative
    deadline_at: Annotated[int, _last]  # same as deadline_ms, preferred name
    request_key: Annotated[str, _last]
    request_id: Annotated[str, _last]
    trace_id: Annotated[str, _last]
    tenant_id: Annotated[Optional[str], _last]
    cancelled: Annotated[bool, _last]
    attempt: Annotated[int, _last]
    checkpoint_hits: Annotated[List[str], _last]
    retry_policy: Annotated[Dict[str,int], _last]
    node_latencies: Annotated[Dict[str,int], _last]
    circuit_breaker_state: Annotated[str, _last]  # closed|open|half_open
    degraded: Annotated[bool, _last]
    error_type: Annotated[Optional[str], _last]  # transient|permanent|None
    error_code: Annotated[Optional[str], _last]  # e.g. crs_mismatch, coreg_ssim_below_threshold
    # test injection (§4) — not in production, used by synthetic harness
    _test_inject: Annotated[Optional[Dict[str, Any]], _last]
    # Phase B — spatial memory / RAG
    turn_history: Annotated[List[Dict[str, Any]], _last]
    entity_registry: Annotated[Dict[str, str], _last]
    last_spectral_indices: Annotated[Dict[str, float], _last]
    last_change_pair: Annotated[Optional[List[str]], _last]
    coreference_map: Annotated[Dict[str, Any], _last]
    last_crop_path: Annotated[Optional[str], _last]
    tmp_files: Annotated[List[str], _last]
    _needs_retry: Annotated[Optional[bool], _last]

def new_state(session_id: str, query: str, assets: List[Dict[str,Any]] | None = None, image_ids: List[str] | None = None, user_id: str | None = None) -> GraphState:
    return GraphState(
        session_id=session_id,
        user_id=user_id,
        query=query,
        assets=assets or [],
        image_ids=image_ids or [],
        task_type="unknown",
        plan={},
        task_output=None,
        final_result=None,
        confidence=None,
        error=None,
        error_log=[],
        retry_count=0,
        execution_trace=[],
        validation_passed=False,
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
        deadline_at=0,
        request_key="",
        request_id="",
        trace_id="",
        tenant_id=None,
        cancelled=False,
        attempt=1,
        checkpoint_hits=[],
        retry_policy={"max_transient": 2, "max_confidence": 2, "max_coreg": 2},
        _needs_retry=None,  # ephemeral flag for pipeline conditional
        node_latencies={},
        circuit_breaker_state="closed",
        degraded=False,
        error_type=None,
        error_code=None,
        _test_inject=None,
        turn_history=[],
        entity_registry={},
        last_spectral_indices={},
        last_change_pair=None,
        coreference_map={},
        last_crop_path=None,
        tmp_files=[],
    )

def add_trace(state: GraphState, agent: str, status: str, detail: Dict[str,Any] | None = None, latency_ms: int | None = None):
    entry = {"agent": agent, "status": status, "detail": detail or {}, "latency_ms": latency_ms}
    # ensure list exists
    if "execution_trace" not in state or state["execution_trace"] is None:
        state["execution_trace"] = []
    state["execution_trace"].append(entry)  # type: ignore
