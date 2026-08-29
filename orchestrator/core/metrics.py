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

def snapshot() -> dict:
    with _lock:
        avg = {k: round(sum(v)/len(v),1) if v else 0 for k,v in _latencies.items()}
        p95 = {}
        for k,v in _latencies.items():
            if not v:
                p95[k]=0
                continue
            s = sorted(v)
            idx = int(len(s)*0.95)
            p95[k]= s[min(idx, len(s)-1)]
        return {
            "counters": dict(_counters),
            "avg_ms": avg,
            "p95_ms": p95,
            "errors": dict(_errors),
            "total_requests": _total_requests,
            "total_failed": _total_failed,
            "availability": round(100*(1 - _total_failed/max(1,_total_requests)),2),
        }

def reset():
    global _total_requests, _total_failed
    with _lock:
        _counters.clear()
        _latencies.clear()
        _errors.clear()
        _total_requests = 0
        _total_failed = 0
