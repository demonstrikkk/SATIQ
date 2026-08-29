"""Latency profiling per agent — compute bottleneck, flag slow agents."""
from __future__ import annotations
from typing import List, Dict, Any, Optional

def compute_bottleneck(trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Trace is list of {agent, status, latency_ms}.
    Returns {slowest_agent, latency_ms, pct_of_total, total_ms}
    """
    if not trace:
        return {"slowest_agent": None, "latency_ms": 0, "pct_of_total": 0, "total_ms": 0}
    total = sum(t.get("latency_ms") or 0 for t in trace)
    if total == 0:
        # fallback: count equally
        return {"slowest_agent": trace[-1].get("agent"), "latency_ms": 0, "pct_of_total": 0, "total_ms": 0}
    slowest = max(trace, key=lambda t: t.get("latency_ms") or 0)
    lat = slowest.get("latency_ms") or 0
    pct = round(lat / total * 100, 1) if total else 0
    return {"slowest_agent": slowest.get("agent"), "latency_ms": lat, "pct_of_total": pct, "total_ms": total}

def flag_slow_agents(trace: List[Dict[str, Any]], threshold_ms: int = 2000) -> List[str]:
    return [t.get("agent") for t in trace if (t.get("latency_ms") or 0) >= threshold_ms]

def trace_summary(trace: List[Dict[str, Any]], threshold_ms: int = 2000) -> Dict[str, Any]:
    bottleneck = compute_bottleneck(trace)
    slow = flag_slow_agents(trace, threshold_ms)
    # per-agent breakdown
    breakdown = {t.get("agent"): t.get("latency_ms") for t in trace}
    return {
        "total_ms": bottleneck["total_ms"],
        "slowest_agent": bottleneck["slowest_agent"],
        "pct_of_total": bottleneck["pct_of_total"],
        "slow_agents": slow,
        "breakdown": breakdown,
        "num_agents": len(trace),
        "retry_counts": {t.get("agent"): t.get("detail",{}).get("retries") for t in trace if t.get("detail",{}).get("retries")},
    }
