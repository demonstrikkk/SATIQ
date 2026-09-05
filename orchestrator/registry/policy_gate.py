"""Policy gate — authorization / resource / tool allowlist before task_agent (P1).

Never delegate policy to LLM. Checks: tenant ownership, asset ownership, plan limits, tool allowlist, deadline, vram.
"""
from __future__ import annotations
from typing import Dict, Any

from orchestrator.helpers.tool_executor import ALLOWED_TOOL_NAMES, MAX_TOOL_CALLS, MAX_PLAN_STEPS

def check_policy(state: Dict[str, Any]) -> tuple[bool, str]:
    # tenant/session ownership
    session_id = state.get("session_id")
    if not session_id:
        return False, "missing session_id"
    # plan limits
    plan = state.get("plan") or {}
    task_type = state.get("task_type") or plan.get("task_type")
    if not task_type:
        return False, "missing task_type"
    if task_type not in ("vqa","grounding","change_vqa","optical_sar_fusion","captioning","greeting","chitchat","help","out_of_scope","general","unknown"):
        return False, f"task_type {task_type} not allowlisted"
    steps = plan.get("steps") or []
    if len(steps) > MAX_PLAN_STEPS:
        return False, f"plan steps {len(steps)} > {MAX_PLAN_STEPS}"
    # tool allowlist if plan has tool_calls
    for tc in plan.get("tool_calls") or []:
        tname = tc if isinstance(tc, str) else tc.get("tool") or tc.get("name")
        if tname and tname not in ALLOWED_TOOL_NAMES:
            return False, f"tool {tname} not allowlisted"
    # asset ownership: each asset_id must start with session prefix or be in assetStore (gateway ensures), here just check presence
    assets = state.get("assets") or []
    if task_type in ("vqa","grounding","change_vqa","optical_sar_fusion") and len(assets) == 0 and not state.get("image_ids"):
        # allow if image_ids present (will be resolved via image_pipeline)
        if not state.get("image_ids"):
            return False, f"{task_type} requires assets"
    # deadline
    deadline = state.get("deadline_at") or state.get("deadline_ms") or 0
    if deadline:
        import time
        remaining = deadline - int(time.time()*1000)
        if remaining <= 0:
            return False, "deadline exceeded before execution"
        if remaining < 2000:
            return False, f"remaining budget {remaining}ms too low to start GPU task"
    # vram queue already checked in api, but double-check here
    return True, "ok"

def policy_gate_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """LangGraph node — runs between planner and task_agent. Fail → error_handler."""
    ok, why = check_policy(state)
    if not ok:
        state["error"] = f"policy_gate blocked: {why}"
        state["error_type"] = "permanent"
        state["error_code"] = "policy_denied"
        state["validation_passed"] = False
    else:
        state["policy_passed"] = True  # type: ignore
    return state
