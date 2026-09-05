"""Vision Encoder Service — pluggable, no dummy mocks.

Until models/vision encoders are linked, this service returns a degraded stub
that does NOT invent embeddings as real — it marks degraded=True so pipeline
can still reach task_agent where MODEL_NOT_LINKED will be raised honestly.
For tasks that skip vision (greeting/chitchat) this path is never hit.
"""
from __future__ import annotations
import time
from typing import Dict, Any, List
from orchestrator.core.errors import NodeTimeoutError
from orchestrator.core import circuit_breaker as cb

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
    """No-mock encoder — returns degraded placeholder, real work happens in model_adapter."""
    if cb.vision_circuit.is_open():
        from orchestrator.core.errors import CircuitOpenError
        raise CircuitOpenError("vision-encoder circuit open")
    t0 = time.time()
    # No real encoder linked yet — return degraded empty that downstream will handle
    # Do NOT call dummy_encoders — honest degraded signal
    result: Dict[str, Any] = {"_degraded": True, "encoder": encoder, "count": len(tiles), "note": "vision encoder not linked — awaiting models/*/inference.py"}
    elapsed = int((time.time() - t0) * 1000)
    if elapsed > timeout_ms:
        cb.vision_circuit.record_failure()
        raise NodeTimeoutError("vision_encoder", budget_ms=timeout_ms, elapsed_ms=elapsed)
    cb.vision_circuit.record_success()
    return result
