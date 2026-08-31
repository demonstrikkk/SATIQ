"""ModelManager — load each model exactly once per process (thread-safe).

Per TASK PROMPT §3, all 4 capabilities must register their loader via
ModelManager().get(name, loader_fn) so weights stay GPU-resident across requests.
Existing dummy code has no manager; this extends without duplicating.
"""
from __future__ import annotations
import threading
from typing import Callable, Dict, Any


class ModelManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._models: Dict[str, Any] = {}
                    cls._instance._load_counts: Dict[str, int] = {}
        return cls._instance

    def get(self, name: str, loader_fn: Callable[[], Any]) -> Any:
        if name not in self._models:
            with self._lock:
                if name not in self._models:
                    self._models[name] = loader_fn()
                    self._load_counts[name] = self._load_counts.get(name, 0) + 1
        return self._models[name]

    def clear(self, name: str | None = None):
        with self._lock:
            if name:
                self._models.pop(name, None)
                self._load_counts.pop(name, None)
            else:
                self._models.clear()
                self._load_counts.clear()

    def load_count(self, name: str) -> int:
        return self._load_counts.get(name, 0)

    def is_loaded(self, name: str) -> bool:
        return name in self._models


manager = ModelManager()
