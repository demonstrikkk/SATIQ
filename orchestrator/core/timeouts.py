"""Timeout budgets (§2.3) — deadline_ms propagated via GraphState."""
from __future__ import annotations
import time

# 8-node LangGraph state graph — 7 happy + terminal error, bounded retry (MAX_ATTEMPTS=2 total)
MAX_ATTEMPTS = 2  # total attempts: 1 initial + 1 retry = 2; retries = MAX_ATTEMPTS-1
MAX_REFLECTION_ITERATIONS = MAX_ATTEMPTS  # alias for docs compat

# Per-node budgets (ms) — total 45s, per-node tight
BUDGETS_MS: dict[str, int] = {
    "input_validator": 400,
    "coreference_resolver": 100,
    "router": 2500,
    "planner": 2500,
    "task_agent": 8000,
    "post_processing": 800,
    "response_composer": 4000,
    "error_handler": 400,
}
TOTAL_BUDGET_MS = 45000

def _now_ms() -> int:
    return int(time.time() * 1000)

def deadline_exceeded(deadline_ms: int) -> bool:
    """True if wall clock has passed the absolute deadline."""
    if not deadline_ms:
        return False
    return _now_ms() > deadline_ms

def remaining_ms(deadline_ms: int) -> int:
    # deadline_ms is authoritative (deadline_at), derived remaining
    if not deadline_ms:
        return TOTAL_BUDGET_MS
    return max(0, deadline_ms - _now_ms())

def deadline_at_to_remaining(deadline_at: int) -> int:
    """Alias: deadline_at is truth, remaining is derived."""
    return remaining_ms(deadline_at)

def init_deadline() -> int:
    return _now_ms() + TOTAL_BUDGET_MS

def check_deadline_or_raise(deadline_ms: int, node: str):
    """Raise NodeTimeoutError if deadline already exceeded before node starts."""
    if deadline_exceeded(deadline_ms):
        from orchestrator.core.errors import NodeTimeoutError
        budget = BUDGETS_MS.get(node, 1000)
        elapsed = budget  # best-effort; exact elapsed not tracked per-node
        raise NodeTimeoutError(node, budget_ms=budget, elapsed_ms=elapsed)
