"""Resilience errors: typed timeout + transient/permanent classification (§2.3/2.4/2.7)."""
from __future__ import annotations

class NodeTimeoutError(Exception):
    """Raised when a node exceeds its deadline budget — transient, retryable."""
    def __init__(self, node: str, budget_ms: int, elapsed_ms: int | None = None):
        self.node = node
        self.budget_ms = budget_ms
        self.elapsed_ms = elapsed_ms
        super().__init__(f"{node} timeout after {elapsed_ms or budget_ms}ms (budget {budget_ms}ms)")

class RateLimitError(Exception):
    """429 / backpressure — transient."""
    pass

class CircuitOpenError(Exception):
    """Circuit breaker open — transient (degraded mode)."""
    pass

# Permanent error codes → never retry (short-circuit to structured error)
PERMANENT_CODES = {
    "crs_mismatch",
    "malformed_geotiff",
    "unsupported_sensor",
    "encoder_modality_mismatch",
    "band_count_mismatch",
    "schema_validation_failed",
    "coreg_ssim_below_threshold",  # after max_coreg retries consumed
    "unsupported_band_count",
    "empty_query",
    "invalid_task_type",
}

TRANSIENT_CODES = {
    "node_timeout",
    "rate_limit_429",
    "connection_reset",
    "gpu_oom",
    "fusion_llm_timeout",
    "vision_encoder_timeout",
    "circuit_open",  # caller should treat as transient degraded
    "coreg_retryable",  # ssim failure while retries remain
}

def classify_error_code(code: str | None) -> str:
    """Return 'permanent' | 'transient'."""
    if not code:
        return "transient"
    c = code.lower()
    if c in PERMANENT_CODES:
        return "permanent"
    if c in TRANSIENT_CODES:
        return "transient"
    # heuristic fallback: inspect substrings
    if any(k in c for k in ("timeout", "oom", "429", "reset", "connection", "unavailable", "retryable")):
        return "transient"
    return "permanent"

def classify_exception(exc: Exception) -> tuple[str, str]:
    """Inspect exception → (error_type, error_code)."""
    if isinstance(exc, NodeTimeoutError):
        return "transient", "node_timeout"
    if isinstance(exc, RateLimitError):
        return "transient", "rate_limit_429"
    if isinstance(exc, CircuitOpenError):
        return "transient", "circuit_open"
    msg = str(exc).lower()
    if "crs mismatch" in msg:
        return "permanent", "crs_mismatch"
    if "unsupported sensor" in msg or "unsupported_sensor" in msg:
        return "permanent", "unsupported_sensor"
    if "encoder_modality" in msg:
        return "permanent", "encoder_modality_mismatch"
    if "band" in msg:
        return "permanent", "band_count_mismatch"
    if "ssim" in msg:
        # coreg after exhausting retries → caller should have already classified
        return "permanent", "coreg_ssim_below_threshold"
    if "timeout" in msg or "oom" in msg or "429" in msg:
        return "transient", "node_timeout"
    return "transient", exc.__class__.__name__.lower()
