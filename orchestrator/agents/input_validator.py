"""Agent 1: Input Validator — deterministic, no LLM."""
from __future__ import annotations
import time
from typing import Dict, Any
from orchestrator.models.graph_state import GraphState, add_trace

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

    # basic checks
    if not query:
        state["error"] = "query is required"
        state["validation_passed"] = False
        add_trace(state, "input_validator", "failed", {"reason": "empty query"}, latency_ms=int((time.time()-t0)*1000))
        return state
    if len(query) > 4000:
        state["error"] = "query exceeds 4000 chars"
        state["validation_passed"] = False
        add_trace(state, "input_validator", "failed", {"reason": "too_long"}, latency_ms=int((time.time()-t0)*1000))
        return state

    # asset presence check
    if not assets and not image_ids:
        # allow text-only? But per spec, most tasks need image
        # we flag but not hard fail — router will handle
        pass

    # CRS hard gate (safety-critical)
    mismatch = _crs_mismatch(assets)
    if mismatch:
        state["error"] = mismatch
        state["validation_passed"] = False
        add_trace(state, "input_validator", "failed", {"reason": mismatch, "assets": assets}, latency_ms=int((time.time()-t0)*1000))
        # also push to error_log
        state.setdefault("error_log", []).append(mismatch)  # type: ignore
        return state

    # modality check: if assets provided, ensure at least one has modality
    # pairing check for bi-temporal / cross-modal will be done in planner, not here
    # resolution/bbox sanity
    for a in assets:
        gsd = a.get("gsd")
        if gsd is not None and gsd <= 0:
            state["error"] = f"invalid GSD {gsd} for asset {a.get('asset_id')}"
            state["validation_passed"] = False
            add_trace(state, "input_validator", "failed", {"asset": a}, latency_ms=int((time.time()-t0)*1000))
            return state

    state["validation_passed"] = True
    state["error"] = None
    add_trace(state, "input_validator", "ok", {"query_len": len(query), "num_assets": len(assets)}, latency_ms=int((time.time()-t0)*1000))
    return state
