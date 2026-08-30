"""Decoupled event broadcaster so graph nodes can emit live events
(answer tokens, progress) to the API layer without importing the app.

The API (api/main.py) registers its `_broadcast` implementation at startup.
Graph nodes `await emit(session_id, event, payload)`. If no broadcaster is
registered (e.g. unit tests, sync CLI), emit is a safe no-op. The registered
broadcaster may be sync or async (coroutine) — emit awaits coroutines.
"""
from __future__ import annotations
from typing import Any, Callable, Optional, Awaitable, Union

_BROADCASTER: Optional[Callable[[str, str, dict], Union[None, Awaitable[None]]]] = None


def register_broadcaster(fn: Callable[[str, str, dict], Union[None, Awaitable[None]]]) -> None:
    global _BROADCASTER
    _BROADCASTER = fn


async def emit(session_id: str, event: str, payload: dict) -> None:
    if _BROADCASTER is not None and session_id:
        try:
            res = _BROADCASTER(session_id, event, payload)
            if hasattr(res, "__await__"):
                await res
        except Exception:
            # never let event emission break the pipeline
            pass
