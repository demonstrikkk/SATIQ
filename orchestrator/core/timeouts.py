"""Timeout budgets (§2.3) — deadline_ms propagated via GraphState."""
from __future__ import annotations
import time

# Per-node budgets (ms), total ~15s — tune against real hardware via profiling.
BUDGETS_MS: dict[str, int] = {
    "input_validator": 200,
    "preprocessing": 2000,
    "encoder_selector": 200,
    "encoder_compat": 200,
    "coreg_gate": 300,
    "vision_encoder": 4000,
    "fusion": 6000,
    "task_agent": 2000,
    "tile_manager": 500,
    "post_processing": 500,
    "response_composer": 600,
    "error_handler": 200,
    "router": 800,
    "planner": 1000,
}
TOTAL_BUDGET_MS = 15000

def _now_ms() -> int:
    return int(time.time() * 1000)

def deadline_exceeded(deadline_ms: int) -> bool:
    """True if wall clock has passed the absolute deadline."""
    if not deadline_ms:
        return False
    return _now_ms() > deadline_ms

def remaining_ms(deadline_ms: int) -> int:
    if not deadline_ms:
        return TOTAL_BUDGET_MS
    return max(0, deadline_ms - _now_ms())

def check_deadline_or_raise(deadline_ms: int, node: str):
    """Raise NodeTimeoutError if deadline already exceeded before node starts."""
    if deadline_exceeded(deadline_ms):
        from orchestrator.core.errors import NodeTimeoutError
        budget = BUDGETS_MS.get(node, 1000)
        raise NodeTimeoutError(node, budget_ms=budget, elapsed_ms=budget)
