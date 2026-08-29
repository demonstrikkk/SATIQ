"""Entry-point queue gate — Redis semaphore with in-memory fallback.

Production: Redis INCR/DECR; for dummy/tests, in-memory counter so no Redis required.
"""
from __future__ import annotations
import os
import threading
import time

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_PIPELINES", "4"))
# also support queue depth limit
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", str(MAX_CONCURRENT)))

_active = 0
_lock = threading.Lock()
_redis_client = None  # lazy

def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    try:
        import redis  # type: ignore
        url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        c = redis.from_url(url, socket_connect_timeout=0.5, socket_timeout=0.5)
        c.ping()
        _redis_client = c
        return c
    except Exception:
        _redis_client = False  # type: ignore
        return None

def get_limits() -> dict:
    mc = int(os.getenv("MAX_CONCURRENT_PIPELINES", str(MAX_CONCURRENT)))
    qd = int(os.getenv("MAX_QUEUE_DEPTH", str(MAX_QUEUE_DEPTH)))
    return {"max_concurrent": mc, "max_queue_depth": qd}

def active_count() -> int:
    # Prefer Redis if available for accurate cross-process count
    r = _get_redis()
    if r is not None:
        try:
            v = r.get("satiq:queue:active")
            return int(v) if v is not None else 0
        except Exception:
            pass
    with _lock:
        return _active

def acquire() -> bool:
    lim = get_limits()
    cap = lim["max_queue_depth"]
    # Try Redis INCR with check
    r = _get_redis()
    if r is not None:
        try:
            # Use Lua-like: INCR then check, DECR if over cap
            cur = r.incr("satiq:queue:active")
            if cur is not None and int(cur) > cap:
                r.decr("satiq:queue:active")
                return False
            # set TTL so stale keys expire if process crashes
            r.expire("satiq:queue:active", 3600)
            return True
        except Exception:
            pass
    # Fallback in-memory
    global _active
    with _lock:
        if _active >= cap:
            return False
        _active += 1
        return True

def release():
    r = _get_redis()
    if r is not None:
        try:
            # DECR but not below 0
            v = r.decr("satiq:queue:active")
            if v is not None and int(v) < 0:
                r.set("satiq:queue:active", 0)
            return
        except Exception:
            pass
    global _active
    with _lock:
        _active = max(0, _active - 1)

def reset():
    r = _get_redis()
    if r is not None:
        try:
            r.delete("satiq:queue:active")
        except Exception:
            pass
    global _active, _redis_client
    with _lock:
        _active = 0
    # keep _redis_client cached (don't reset to None, keep false sentinel)
