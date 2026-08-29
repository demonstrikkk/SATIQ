"""Redis session state with in-memory fallback (so pipeline works without Redis)."""
from __future__ import annotations
import json
import time
from typing import Any, Dict, List, Optional

try:
    import redis.asyncio as aioredis  # type: ignore
except Exception:
    aioredis = None  # type: ignore

class SessionState:
    """Simple wrapper: session:{sid}:state hash, tiles, coreg, error_log, events."""
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_url = redis_url
        self._client = None
        self._mem: Dict[str, Any] = {}  # fallback
        self._mem_lists: Dict[str, List[Any]] = {}
        self._mem_hash: Dict[str, Dict[str, Any]] = {}

    async def _get_client(self):
        if aioredis is None:
            return None
        if self._client is None:
            try:
                self._client = aioredis.from_url(self.redis_url, decode_responses=True, socket_connect_timeout=1)
                await self._client.ping()
            except Exception:
                self._client = None
                return None
        return self._client

    # --- hash ops ---
    async def hset(self, key: str, field: str, value: Any):
        c = await self._get_client()
        if c:
            await c.hset(key, field, json.dumps(value) if not isinstance(value, str) else value)
            await c.expire(key, 3600)
        else:
            self._mem_hash.setdefault(key, {})[field] = value

    async def hget(self, key: str, field: str) -> Optional[Any]:
        c = await self._get_client()
        if c:
            v = await c.hget(key, field)
            if v is None:
                return None
            try:
                return json.loads(v)
            except Exception:
                return v
        return self._mem_hash.get(key, {}).get(field)

    async def hgetall(self, key: str) -> Dict[str, Any]:
        c = await self._get_client()
        if c:
            d = await c.hgetall(key)
            out = {}
            for k, v in d.items():
                try:
                    out[k] = json.loads(v)
                except Exception:
                    out[k] = v
            return out
        return dict(self._mem_hash.get(key, {}))

    # --- list ops ---
    async def lpush(self, key: str, value: Any):
        c = await self._get_client()
        if c:
            await c.lpush(key, json.dumps(value) if not isinstance(value, str) else value)
            await c.expire(key, 3600)
        else:
            self._mem_lists.setdefault(key, []).insert(0, value)

    async def lrange(self, key: str, start=0, end=-1):
        c = await self._get_client()
        if c:
            vals = await c.lrange(key, start, end)
            out = []
            for v in vals:
                try:
                    out.append(json.loads(v))
                except Exception:
                    out.append(v)
            return out
        lst = self._mem_lists.get(key, [])
        if end == -1:
            return lst[start:]
        return lst[start:end+1]

    # --- pub/sub for WS (in-memory fanout) ---
    _subscribers: Dict[str, List] = {}

    async def publish(self, channel: str, event: Dict[str, Any]):
        c = await self._get_client()
        if c:
            try:
                await c.publish(channel, json.dumps(event))
            except Exception:
                pass
        # in-memory
        for cb in self._subscribers.get(channel, []):
            try:
                cb(event)
            except Exception:
                pass

    def subscribe(self, channel: str, cb):
        self._subscribers.setdefault(channel, []).append(cb)
        def unsub():
            try:
                self._subscribers[channel].remove(cb)
            except Exception:
                pass
        return unsub

# singleton
session_state = SessionState()
