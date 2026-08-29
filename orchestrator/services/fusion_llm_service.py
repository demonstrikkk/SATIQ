"""Fusion LLM Service interface (§2.1 split).

Wraps Qwen 3.5 9B + adapter (or Groq). Called with hard timeout (§2.3: 6000ms).
For dummy testing, the service delegates to dummy_fusion — the interface boundary is what matters.
"""
from __future__ import annotations
import time
from typing import Dict, Any
from orchestrator.dummy.dummy_fusion import run_fusion
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
    if cb.fusion_circuit.is_open():
        raise CircuitOpenError("fusion-llm circuit open")
    t0 = time.time()
    try:
        result = run_fusion(embeddings, query or "", method="attention")
        elapsed = int((time.time() - t0)*1000)
        if elapsed > timeout_ms:
            cb.fusion_circuit.record_failure()
            raise NodeTimeoutError("fusion", budget_ms=timeout_ms, elapsed_ms=elapsed)
        cb.fusion_circuit.record_success()
        return result
    except (NodeTimeoutError, CircuitOpenError):
        cb.fusion_circuit.record_failure()
        raise
    except Exception:
        cb.fusion_circuit.record_failure()
        raise
