"""Entry-point queue gate (§2.2 audit fix: semaphore counter).

Production: replace with Redis Streams / SQS; for dummy, in-memory counter + max depth.
Wrap background_tasks.add_task(run_pipeline) with acquire() → 429, release() on finish.
"""
from __future__ import annotations
import os
import threading

MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_PIPELINES", "4"))
# also support queue depth limit
MAX_QUEUE_DEPTH = int(os.getenv("MAX_QUEUE_DEPTH", str(MAX_CONCURRENT)))

_active = 0
_lock = threading.Lock()

def get_limits() -> dict:
    # re-read env for test overrides via monkeypatch
    mc = int(os.getenv("MAX_CONCURRENT_PIPELINES", str(MAX_CONCURRENT)))
    qd = int(os.getenv("MAX_QUEUE_DEPTH", str(MAX_QUEUE_DEPTH)))
    return {"max_concurrent": mc, "max_queue_depth": qd}

def active_count() -> int:
    with _lock:
        return _active

def acquire() -> bool:
    """Try to acquire a slot. Returns False → 429 backpressure."""
    global _active
    lim = get_limits()
    cap = lim["max_queue_depth"]
    with _lock:
        if _active >= cap:
            return False
        _active += 1
        return True

def release():
    global _active
    with _lock:
        _active = max(0, _active - 1)

def reset():
    global _active
    with _lock:
        _active = 0
