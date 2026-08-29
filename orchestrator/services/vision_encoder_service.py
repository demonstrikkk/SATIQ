"""Vision Encoder Service interface (§2.1 split).

The LangGraph controller calls this over HTTP/gRPC with a hard timeout.
For dummy testing, the service is a local stub calling dummy_encoders — the interface boundary is what matters.
Production: implement as FastAPI service with /health endpoints, ≥2 replicas per encoder type.
"""
from __future__ import annotations
import time
from typing import Dict, Any, List
from orchestrator.dummy.dummy_encoders import run_satmae, run_ssl4eo, run_prithvi, run_croma
from orchestrator.core.errors import NodeTimeoutError
from orchestrator.core import circuit_breaker as cb

def _wrap_satmae(tiles): return {"satmae": run_satmae(tiles)}
def _wrap_ssl4eo(tiles): return {"ssl4eo": run_ssl4eo(tiles, modality="optical")}
def _wrap_prithvi(tiles): return {"prithvi": run_prithvi(tiles)}
def _wrap_croma(tiles):
    # croma expects optical/sar split — handled outside but pass through
    # for service we just call run_croma with split heuristic
    optical = [t for t in tiles if t.get("modality") in ("optical","multispectral")]
    sar = [t for t in tiles if t.get("modality")=="sar"]
    if not optical and not sar and len(tiles)>=2:
        optical = tiles[:1]; sar = tiles[1:]
    elif not optical and tiles:
        optical = tiles; sar = tiles
    return run_croma(optical, sar)

ENCODER_FUNCS = {
    "satmae": _wrap_satmae,
    "ssl4eo": _wrap_ssl4eo,
    "prithvi": _wrap_prithvi,
    "croma": _wrap_croma,
}

# health flag — upload health.py controls? For now simple in-memory
_HEALTHY = True
_READY = True

def set_health(healthy: bool, ready: bool | None = None):
    global _HEALTHY, _READY
    _HEALTHY = healthy
    if ready is not None:
        _READY = ready

def health_live() -> Dict[str, Any]:
    return {"status": "healthy" if _HEALTHY else "unhealthy", "service": "vision-encoder-service", "healthy": _HEALTHY}

def health_ready() -> Dict[str, Any]:
    ready = _HEALTHY and _READY and not cb.vision_circuit.is_open()
    status = 200 if ready else 503
    return {"status": "ready" if ready else "not_ready", "circuit": cb.vision_circuit.state, "http_status": status}

def encode(tiles: List[Dict[str, Any]], encoder: str, timeout_ms: int = 4000) -> Dict[str, Any]:
    """Call vision encoder with hard timeout. Raises NodeTimeoutError on exceed."""
    if cb.vision_circuit.is_open():
        # degraded: return empty embeddings with flag
        from orchestrator.core.errors import CircuitOpenError
        raise CircuitOpenError("vision-encoder circuit open")
    fn = ENCODER_FUNCS.get(encoder.lower(), encode_with_satmae)
    t0 = time.time()
    try:
        # simulate via dummy encoders (fast, <50ms) — real hardware would enforce timeout via asyncio.wait_for
        result = fn(tiles)
        elapsed = int((time.time() - t0)*1000)
        if elapsed > timeout_ms:
            cb.vision_circuit.record_failure()
            raise NodeTimeoutError("vision_encoder", budget_ms=timeout_ms, elapsed_ms=elapsed)
        cb.vision_circuit.record_success()
        return result
    except NodeTimeoutError:
        cb.vision_circuit.record_failure()
        raise
    except Exception as e:
        # unexpected → count toward circuit but re-raise
        cb.vision_circuit.record_failure()
        raise
