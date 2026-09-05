"""Query cache — Redis SETEX with request_key + model in key, X-Cache header support.

Uses compute_request_key from checkpoint.py (order-independent) plus composer model hash.
TTL = settings.query_cache_ttl (3600 default).
In-memory fallback for tests without Redis.
"""
from __future__ import annotations
import hashlib
import json
import os
import time
from typing import Any, Dict, Optional

from orchestrator.core.config import get_settings

_mem_cache: Dict[str, tuple[float, Any]] = {}  # key -> (expiry, value)


def _redis():
    try:
        import redis  # type: ignore
        url = os.getenv("REDIS_URL", get_settings().redis_url)
        c = redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5, decode_responses=True)
        c.ping()
        return c
    except Exception:
        return None


def cache_key(request_key: str, task_type: str, model: str) -> str:
    mh = hashlib.sha256(model.encode()).hexdigest()[:8]
    return f"satiq:qcache:{request_key}:{task_type}:{mh}"


def get(key: str) -> Optional[Dict[str, Any]]:
    r = _redis()
    if r is not None:
        try:
            v = r.get(key)
            if v:
                return json.loads(v)
        except Exception:
            pass
    # mem fallback
    ent = _mem_cache.get(key)
    if ent and ent[0] > time.time():
        return ent[1]
    elif ent:
        _mem_cache.pop(key, None)
    return None


def set(key: str, value: Dict[str, Any], ttl: int | None = None) -> None:
    s = get_settings()
    ttl = ttl or int(getattr(s, "query_cache_ttl", 3600))
    r = _redis()
    if r is not None:
        try:
            r.setex(key, ttl, json.dumps(value, default=str))
            return
        except Exception:
            pass
    _mem_cache[key] = (time.time() + ttl, value)
    # cap mem
    if len(_mem_cache) > 512:
        oldest = min(_mem_cache.items(), key=lambda kv: kv[1][0])[0]
        _mem_cache.pop(oldest, None)


def clear():
    _mem_cache.clear()
    r = _redis()
    if r is not None:
        try:
            for k in r.scan_iter("satiq:qcache:*"):
                r.delete(k)
        except Exception:
            pass
