"""Fusion LLM Service — deprecated (fusion handled inside Model4Engine, no external service)."""
from __future__ import annotations
import time
from typing import Dict, Any
from orchestrator.core.errors import NodeTimeoutError, CircuitOpenError
from orchestrator.core import circuit_breaker as cb

_HEALTHY = True
_READY = True

def set_health(healthy: bool, ready: bool | None = None):
    global _HEALTHY, _READY
    _HEALTHY = healthy
    if ready is not None:
        _READY = ready

def health_live() -> Dict[str, Any]:
    return {"status": "healthy" if _HEALTHY else "unhealthy", "service": "fusion-llm-service", "healthy": _HEALTHY}

def health_ready() -> Dict[str, Any]:
    ready = _HEALTHY and _READY and not cb.fusion_circuit.is_open()
    status = 200 if ready else 503
    return {"status": "ready" if ready else "not_ready", "circuit": cb.fusion_circuit.state, "http_status": status}

def fuse(embeddings: Dict[str, Any], timeout_ms: int = 6000, query: str | None = None) -> Dict[str, Any]:
    # Deprecated — real fusion is inside Model4 shim, not external service
    return {"_degraded": True, "note": "fusion_llm_service deprecated — use Model4Engine directly"}
