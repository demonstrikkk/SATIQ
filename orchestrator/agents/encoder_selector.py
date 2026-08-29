"""Agent 4: Encoder Selector — rule-based, no LLM. TTL cache §2.9."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.ttl_cache import encoder_cache
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency

def encoder_selector_node(state: GraphState) -> GraphState:
    t0 = time.time()
    rk = state.get("request_key") or ""
    task_type = state.get("task_type","vqa")
    assets = state.get("assets") or []
    modalities = [a.get("modality","unknown") for a in assets]
    # TTL cache: modality→encoder table (§2.9)
    try:
        cache_key = f"{task_type}:{'|'.join(sorted(modalities))}"
        cached = encoder_cache.get(cache_key)
        if cached and isinstance(cached, dict) and cached.get("encoder"):
            state["encoder"] = cached["encoder"]
            state.setdefault("checkpoint_hits", []).append("encoder_selector_cache")  # type: ignore
            lat = int((time.time()-t0)*1000)
            state.setdefault("node_latencies", {})["encoder_selector"] = lat  # type: ignore
            add_trace(state, "encoder_selector", "ok_cached", {"encoder": cached["encoder"], "modalities": modalities, "task": task_type}, latency_ms=lat)
            log_node("encoder_selector", rk, "ok_cached", lat, None, {"cached": True})
            record_node_latency("encoder_selector", lat)
            return state
    except Exception:
        pass
    has_sar = "sar" in modalities
    has_optical = any(m in ("optical","multispectral") for m in modalities)
    # selection logic
    if task_type == "optical_sar_fusion" and has_sar and has_optical:
        encoder = "croma"
    elif task_type == "change_vqa":
        encoder = "prithvi"  # bi-temporal FM
    elif task_type == "grounding":
        encoder = "satmae"
    elif task_type == "vqa":
        # choose ssl4eo for multispectral else satmae
        if has_optical and len(modalities)==1 and modalities[0]=="multispectral":
            encoder = "ssl4eo"
        else:
            encoder = "satmae"
    else:
        encoder = "satmae"

    state["encoder"] = encoder
    try:
        cache_key = f"{task_type}:{'|'.join(sorted(modalities))}"
        encoder_cache.set(cache_key, {"encoder": encoder})
    except Exception:
        pass
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["encoder_selector"] = lat  # type: ignore
    add_trace(state, "encoder_selector", "ok", {"encoder": encoder, "modalities": modalities, "task": task_type}, latency_ms=lat)
    log_node("encoder_selector", rk, "ok", lat, None, {"encoder": encoder})
    record_node_latency("encoder_selector", lat)
    return state
