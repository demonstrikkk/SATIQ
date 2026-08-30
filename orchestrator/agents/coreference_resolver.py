"""Coreference resolver — pure Python, zero LLM calls. Replaces aliases with resolved coords."""
from __future__ import annotations
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import check_deadline_or_raise
import time

def coreference_resolver_node(state: GraphState) -> GraphState:
    t0 = time.time()
    # coreference is <1ms pure Python, no deadline needed
    query = state.get("query", "")
    cr_map = state.get("coreference_map") or {}
    entity_reg = state.get("entity_registry") or {}
    all_refs = {**cr_map, **entity_reg}
    resolved = query
    for alias, resolution in all_refs.items():
        if alias.lower() in query.lower():
            import re
            pattern = re.compile(re.escape(alias), re.IGNORECASE)
            resolved = pattern.sub(f"[RESOLVED:{resolution}]", resolved)
    if resolved != query:
        state["query"] = resolved  # type: ignore
        state["query_original"] = query  # type: ignore
    add_trace(state, "coreference_resolver", "ok", {"aliases": list(all_refs.keys()), "changed": resolved != query}, latency_ms=int((time.time()-t0)*1000))
    return state
