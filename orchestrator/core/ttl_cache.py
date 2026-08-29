"""TTL caches for Tile Manager AOI and Encoder Selector mapping (§2.9)."""
from __future__ import annotations
import time
from typing import Any, Dict, Optional, Tuple

class TTLCache:
    def __init__(self, ttl_seconds: int = 300, max_entries: int = 256):
        self.ttl = ttl_seconds
        self.max = max_entries
        self._store: Dict[str, Tuple[float, Any]] = {}

    def get(self, key: str) -> Optional[Any]:
        ent = self._store.get(key)
        if not ent:
            return None
        ts, val = ent
        if time.time() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return val

    def set(self, key: str, val: Any):
        if len(self._store) >= self.max:
            # evict oldest
            oldest = min(self._store.items(), key=lambda kv: kv[1][0])[0]
            self._store.pop(oldest, None)
        self._store[key] = (time.time(), val)

    def clear(self):
        self._store.clear()

    def hit(self, key: str) -> bool:
        return self.get(key) is not None

# Singletons
tile_cache = TTLCache(ttl_seconds=300, max_entries=512)  # AOI grid/stitch metadata
encoder_cache = TTLCache(ttl_seconds=600, max_entries=64)  # modality→encoder table
