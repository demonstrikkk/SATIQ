"""Circuit breaker for Qwen/Ollama backend (§2.5 audit fix: at llm_client level).

Closed → open after N consecutive failures in rolling window → half-open probe after cooldown.
When open, resolve_provider returns mock without waiting.

Also used for vision-encoder-service / fusion-llm-service when wrapped.
"""
from __future__ import annotations
import time
import threading

class CircuitBreaker:
    def __init__(self, name: str = "qwen", failure_threshold: int = 5, window_seconds: int = 30, cooldown_seconds: int = 15):
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds
        self._failures: list[float] = []
        self._state: str = "closed"  # closed | open | half_open
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            self._maybe_transition()
            return self._state

    def _prune(self, now: float):
        cutoff = now - self.window_seconds
        self._failures = [t for t in self._failures if t >= cutoff]

    def _maybe_transition(self):
        now = time.time()
        if self._state == "open" and self._opened_at is not None:
            if now - self._opened_at >= self.cooldown_seconds:
                self._state = "half_open"

    def record_success(self):
        with self._lock:
            self._failures.clear()
            self._state = "closed"
            self._opened_at = None

    def record_failure(self):
        with self._lock:
            now = time.time()
            self._failures.append(now)
            self._prune(now)
            self._maybe_transition()
            if self._state == "half_open":
                # probe failed → re-open
                self._state = "open"
                self._opened_at = now
                return
            if len(self._failures) >= self.failure_threshold and self._state == "closed":
                self._state = "open"
                self._opened_at = now

    def allow_request(self) -> bool:
        with self._lock:
            self._maybe_transition()
            return self._state != "open"

    def is_open(self) -> bool:
        return self.state == "open"

    def reset(self):
        with self._lock:
            self._failures.clear()
            self._state = "closed"
            self._opened_at = None

    def snapshot(self) -> dict:
        with self._lock:
            self._maybe_transition()
            self._prune(time.time())
            return {
                "name": self.name,
                "state": self._state,
                "failures_in_window": len(self._failures),
                "threshold": self.failure_threshold,
                "opened_at": self._opened_at,
            }

# Singleton for Qwen backend (audit: one breaker for all 3 Qwen calls)
qwen_circuit = CircuitBreaker(name="qwen", failure_threshold=5, window_seconds=30, cooldown_seconds=15)
# Separate breakers for vision/fusion services when wrapped
vision_circuit = CircuitBreaker(name="vision-encoder", failure_threshold=5, window_seconds=30, cooldown_seconds=15)
fusion_circuit = CircuitBreaker(name="fusion-llm", failure_threshold=5, window_seconds=30, cooldown_seconds=15)

def reset_all():
    qwen_circuit.reset()
    vision_circuit.reset()
    fusion_circuit.reset()
