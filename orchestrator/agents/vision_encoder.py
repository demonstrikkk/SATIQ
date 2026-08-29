"""Agent 8: Vision Encoder — calls vision-encoder-service (§2.1 split) with deadline + checkpoint (§2.3/2.6)."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import BUDGETS_MS, check_deadline_or_raise
from orchestrator.core.checkpoint import save_checkpoint, load_checkpoint, has_checkpoint
from orchestrator.core.structured_logging import log_node
from orchestrator.core.metrics import record_node_latency
from orchestrator.core.errors import NodeTimeoutError, CircuitOpenError
from orchestrator.services.vision_encoder_service import encode as service_encode
from orchestrator.dummy.dummy_encoders import run_satmae, run_ssl4eo, run_prithvi, run_croma  # fallback direct

def vision_encoder_node(state: GraphState) -> GraphState:
    t0 = time.time()
    rk = state.get("request_key") or ""
    # checkpoint hit — clear previous error on resume
    try:
        if rk and has_checkpoint(rk, "vision_encoder"):
            hit = load_checkpoint(rk, "vision_encoder")
            if hit:
                state["embeddings"] = hit.get("embeddings", state.get("embeddings"))
                state["_embeddings_raw"] = hit.get("_embeddings_raw", state.get("_embeddings_raw"))
                state.setdefault("checkpoint_hits", []).append("vision_encoder")  # type: ignore
                state["error"] = None; state["error_type"] = None; state["error_code"] = None
                lat = int((time.time()-t0)*1000)
                state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
                add_trace(state, "vision_encoder", "ok_cached", {"encoder": state.get("encoder"), "request_key": rk}, latency_ms=lat)
                log_node("vision_encoder", rk, "ok_cached", lat, None, {"cached": True})
                record_node_latency("vision_encoder", lat)
                return state
    except Exception:
        pass
    try:
        check_deadline_or_raise(state.get("deadline_ms", 0), "vision_encoder")
    except NodeTimeoutError as e:
        lat = int((time.time()-t0)*1000)
        state["error"] = str(e); state["error_type"]="transient"; state["error_code"]="node_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
        add_trace(state, "vision_encoder", "failed", {"error": str(e), "retry": state["retry_count"]}, latency_ms=lat)
        log_node("vision_encoder", rk, "failed", lat, "transient", {"timeout": True, "retry": state["retry_count"]})
        record_node_latency("vision_encoder", lat, "transient")
        return state
    # test injections — increment retry_count here so after_vision can bound correctly (conditional must not mutate)
    _inj = state.get("_test_inject") or {}
    if isinstance(_inj, dict) and _inj.get("vision_slow"):
        e = NodeTimeoutError("vision_encoder", budget_ms=BUDGETS_MS.get("vision_encoder",4000), elapsed_ms=4001)
        lat = int((time.time()-t0)*1000)
        state["error"] = str(e); state["error_type"]="transient"; state["error_code"]="vision_encoder_timeout"
        # increment retry for bounding
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
        add_trace(state, "vision_encoder", "failed", {"error": "injected slow", "retry": state["retry_count"]}, latency_ms=lat)
        log_node("vision_encoder", rk, "failed", lat, "transient", {"injected": True, "retry": state["retry_count"]})
        record_node_latency("vision_encoder", lat, "transient")
        return state
    if isinstance(_inj, dict) and _inj.get("vision_flaky") and state.get("retry_count",0)==0:
        lat = int((time.time()-t0)*1000)
        state["error"] = "flaky vision encoder (injected)"
        state["error_type"]="transient"; state["error_code"]="vision_encoder_timeout"
        state["retry_count"] = state.get("retry_count",0) + 1
        state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
        add_trace(state, "vision_encoder", "failed", {"error": "flaky injected", "retry": state["retry_count"]}, latency_ms=lat)
        log_node("vision_encoder", rk, "failed", lat, "transient", {"flaky": True, "retry": state["retry_count"]})
        record_node_latency("vision_encoder", lat, "transient")
        return state
    encoder = state.get("encoder","satmae")
    tiles = state.get("tiles") or []
    # split by modality for croma — delegate via service interface (§2.1) with timeout budget
    budget_ms = BUDGETS_MS.get("vision_encoder", 4000)
    try:
        # Use service (handles circuit breaker)
        # service expects tiles + encoder already split; we pass tiles directly and let service dispatch
        # For dummy, service_encode already wraps dummy encoders; fallback to direct if needed
        try:
            # service handles all encoders via single encode(tiles, encoder)
            embeddings_raw = service_encode(tiles, encoder, timeout_ms=budget_ms)
            # service_encode returns dict like {"satmae": [...]} already; if not, fallback
            if isinstance(embeddings_raw, dict) and any(isinstance(v, list) for v in embeddings_raw.values()):
                embeddings = embeddings_raw
            else:
                raise ValueError("service unexpected shape fallback")
        except CircuitOpenError as ce:
            lat = int((time.time()-t0)*1000)
            state["error"] = str(ce); state["error_type"]="transient"; state["error_code"]="circuit_open"
            state["degraded"] = True
            state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
            add_trace(state, "vision_encoder", "failed", {"error": "circuit_open", "encoder": encoder}, latency_ms=lat)
            log_node("vision_encoder", rk, "failed", lat, "transient", {"circuit": True})
            record_node_latency("vision_encoder", lat, "transient")
            return state
        except NodeTimeoutError:
            lat = int((time.time()-t0)*1000)
            state["error"] = f"vision_encoder timeout after {budget_ms}ms"
            state["error_type"]="transient"; state["error_code"]="vision_encoder_timeout"
            state["retry_count"] = state.get("retry_count",0) + 1
            state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
            add_trace(state, "vision_encoder", "failed", {"error": "timeout", "retry": state["retry_count"]}, latency_ms=lat)
            log_node("vision_encoder", rk, "failed", lat, "transient", {"timeout": True, "retry": state["retry_count"]})
            record_node_latency("vision_encoder", lat, "transient")
            return state
        else:
            embeddings = embeddings_raw
    except Exception:
        # fallback direct (service bug) — run via dummy without circuit
        if encoder == "croma":
            optical_tiles = [t for t in tiles if t.get("modality") in ("optical","multispectral")]
            sar_tiles = [t for t in tiles if t.get("modality")=="sar"]
            if not optical_tiles and not sar_tiles and len(tiles)>=2:
                optical_tiles = tiles[:1]; sar_tiles = tiles[1:]
            elif not optical_tiles and tiles:
                optical_tiles = tiles; sar_tiles = tiles
            embeddings = run_croma(optical_tiles, sar_tiles)
        elif encoder == "prithvi":
            embeddings = {"prithvi": run_prithvi(tiles)}
        elif encoder == "ssl4eo":
            emb = run_ssl4eo(tiles, modality="optical")
            embeddings = {"ssl4eo": emb}
        else:
            embeddings = {"satmae": run_satmae(tiles)}
    # store — clear previous transient error on success
    state["error"] = None; state["error_type"] = None; state["error_code"] = None
    state["embeddings"] = {k: {"count": len(v) if isinstance(v, list) else 1, "dim": int(v[0].shape[0]) if isinstance(v, list) and len(v)>0 and hasattr(v[0],"shape") else 768, "_raw": v} for k,v in embeddings.items()} if isinstance(embeddings, dict) else {"default": embeddings}
    state["_embeddings_raw"] = embeddings  # type: ignore
    try:
        if rk:
            save_checkpoint(rk, "vision_encoder", {"embeddings": state["embeddings"], "_embeddings_raw": embeddings})
    except Exception:
        pass
    lat = int((time.time()-t0)*1000)
    state.setdefault("node_latencies", {})["vision_encoder"] = lat  # type: ignore
    add_trace(state, "vision_encoder", "ok", {"encoder": encoder, "num_tiles": len(tiles), "embed_keys": list(embeddings.keys()) if isinstance(embeddings, dict) else ["default"], "request_key": rk}, latency_ms=lat)
    log_node("vision_encoder", rk, "ok", lat, None, {"encoder": encoder})
    record_node_latency("vision_encoder", lat)
    return state
