"""In-memory latency / availability metrics (§3 checklist: per-node + e2e)."""
from __future__ import annotations
import threading
import time
from typing import Dict, List

_lock = threading.Lock()
_counters: Dict[str, int] = {}
_latencies: Dict[str, List[int]] = {}
_errors: Dict[str, int] = {}
_total_requests = 0
_total_failed = 0

def record_node_latency(node: str, latency_ms: int, error_type: str | None = None):
    with _lock:
        _counters[node] = _counters.get(node, 0) + 1
        _latencies.setdefault(node, []).append(latency_ms)
        # keep last 1000 per node
        if len(_latencies[node]) > 1000:
            _latencies[node] = _latencies[node][-1000:]
        if error_type:
            key = f"{node}:{error_type}"
            _errors[key] = _errors.get(key, 0) + 1

def record_request(success: bool):
    global _total_requests, _total_failed
    with _lock:
        _total_requests += 1
        if not success:
            _total_failed += 1

def _pctl(s: List[int], p: float) -> int:
    if not s: return 0
    s = sorted(s)
    idx = int(len(s)*p)
    return s[min(idx, len(s)-1)]

def snapshot(session_id: str | None = None) -> dict:
    with _lock:
        avg = {k: round(sum(v)/len(v),1) if v else 0 for k,v in _latencies.items()}
        p50 = {k: _pctl(v, 0.50) for k,v in _latencies.items()}
        p95 = {k: _pctl(v, 0.95) for k,v in _latencies.items()}
        p99 = {k: _pctl(v, 0.99) for k,v in _latencies.items()}
        # vram telemetry
        vram_peak = 0; vram_queue = 0; vram_permits = 2
        try:
            import torch
            if torch.cuda.is_available():
                vram_peak = int(torch.cuda.max_memory_allocated() / (1024*1024))
        except Exception:
            pass
        try:
            from orchestrator.agents.task_agents import _vram_queue_depth
            vram_queue = _vram_queue_depth()
        except Exception:
            pass
        return {
            "counters": dict(_counters),
            "avg_ms": avg,
            "p50_ms": p50,
            "p95_ms": p95,
            "p99_ms": p99,
            "errors": dict(_errors),
            "total_requests": _total_requests,
            "total_failed": _total_failed,
            "availability": round(100*(1 - _total_failed/max(1,_total_requests)),2),
            "vram": {"peak_mb": vram_peak, "queue_depth": vram_queue, "permits": vram_permits, "max_queue": 4},
            "budget": {"total_ms": 45000, "max_reflection": 2},
            "session_id": session_id,
        }

def reset():
    global _total_requests, _total_failed
    with _lock:
        _counters.clear()
        _latencies.clear()
        _errors.clear()
        _total_requests = 0
        _total_failed = 0
