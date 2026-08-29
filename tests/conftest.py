"""Test fixtures — reset resilience singletons, record latencies for RESULTS.md."""
from __future__ import annotations
import pytest

# results buffer for RESULTS.md auto-generation (audit #9)
_results_buffer: list[dict] = []

@pytest.fixture(autouse=True)
def reset_resilience():
    # reset before each test
    try:
        from orchestrator.core import checkpoint as _cp
        _cp.reset_store()
    except Exception:
        pass
    try:
        from orchestrator.core import circuit_breaker as _cb
        _cb.reset_all()
    except Exception:
        pass
    try:
        from orchestrator.core import queue_gate as _q
        _q.reset()
    except Exception:
        pass
    try:
        from orchestrator.core import metrics as _m
        _m.reset()
    except Exception:
        pass
    try:
        from orchestrator.core.ttl_cache import tile_cache, encoder_cache
        tile_cache.clear(); encoder_cache.clear()
    except Exception:
        pass
    yield
    # after: nothing — record happens in tests themselves

@pytest.fixture
def pipeline():
    from orchestrator.graph.pipeline import get_pipeline
    return get_pipeline()

@pytest.fixture
def new_state():
    from orchestrator.models.graph_state import new_state as _ns
    return _ns

def record_latency_for_results(trace: list[dict], case: str):
    try:
        from orchestrator.helpers.trace import trace_summary
        summary = trace_summary(trace)
        _results_buffer.append({"case": case, "summary": summary, "trace": trace})
    except Exception:
        _results_buffer.append({"case": case, "summary": {}, "trace": trace})

def get_results_buffer():
    return _results_buffer
