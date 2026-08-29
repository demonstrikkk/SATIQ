"""Structured logging (§3 checklist): {node, request_key, status, latency_ms, error_type}."""
from __future__ import annotations
import json
import time
from typing import Any, Dict

def log_node(node: str, request_key: str = "", status: str = "ok", latency_ms: int | None = None, error_type: str | None = None, detail: Dict[str, Any] | None = None):
    rec = {
        "ts": int(time.time()*1000),
        "node": node,
        "request_key": request_key or "",
        "status": status,
        "latency_ms": latency_ms if latency_ms is not None else 0,
        "error_type": error_type or "",
        "detail": detail or {},
    }
    # JSON line to stdout — consumable by log aggregator and RESULTS.md generator
    try:
        print(json.dumps(rec), flush=True)
    except Exception:
        print(f"[{node}] {status} {latency_ms}ms {error_type}", flush=True)
