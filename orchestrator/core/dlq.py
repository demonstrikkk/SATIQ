"""DLQ — Dead Letter Queue for permanently failed tasks.

Redis list satiq:dlq:{session_id} with in-memory fallback.
"""
from __future__ import annotations
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, List

try:
    import redis  # type: ignore
except Exception:
    redis = None  # type: ignore

import os

_DLQ_MEM: List[Dict[str, Any]] = []
_DLQ_MEM_BY_SESSION: Dict[str, List[Dict[str, Any]]] = {}

def _get_redis():
    if redis is None:
        return None
    try:
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        c = redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        c.ping()
        return c
    except Exception:
        return None

def push(session_id: str, payload: Dict[str, Any]) -> None:
    payload = dict(payload)
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    payload.setdefault("session_id", session_id)
    key = f"satiq:dlq:{session_id}"
    r = _get_redis()
    if r is not None:
        try:
            r.lpush(key, json.dumps(payload))
            r.expire(key, 86400 * 7)  # 7 days
            r.lpush("satiq:dlq:all", json.dumps(payload))
            r.ltrim("satiq:dlq:all", 0, 999)
            return
        except Exception:
            pass
    # in-memory fallback
    _DLQ_MEM.append(payload)
    _DLQ_MEM_BY_SESSION.setdefault(session_id, []).append(payload)
    # also write to disk for persistence
    try:
        from pathlib import Path
        p = Path("orchestrator/storage/dlq.jsonl")
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass

def list_all(limit: int = 100) -> List[Dict[str, Any]]:
    r = _get_redis()
    if r is not None:
        try:
            # try global list
            items = r.lrange("satiq:dlq:all", 0, limit - 1)
            if items:
                return [json.loads(x) for x in items]
            # fallback scan keys
            keys = r.keys("satiq:dlq:*")
            out = []
            for k in keys[:20]:
                vals = r.lrange(k, 0, limit - 1)
                for v in vals:
                    out.append(json.loads(v))
                    if len(out) >= limit:
                        break
            return out[:limit]
        except Exception:
            pass
    return list(reversed(_DLQ_MEM[-limit:]))

def list_by_session(session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    r = _get_redis()
    if r is not None:
        try:
            vals = r.lrange(f"satiq:dlq:{session_id}", 0, limit - 1)
            return [json.loads(x) for x in vals]
        except Exception:
            pass
    return list(reversed(_DLQ_MEM_BY_SESSION.get(session_id, [])[-limit:]))

def clear():
    _DLQ_MEM.clear()
    _DLQ_MEM_BY_SESSION.clear()
    r = _get_redis()
    if r is not None:
        try:
            keys = r.keys("satiq:dlq:*")
            if keys:
                r.delete(*keys)
        except Exception:
            pass
    try:
        from pathlib import Path
        p = Path("orchestrator/storage/dlq.jsonl")
        if p.exists():
            p.unlink()
    except Exception:
        pass
