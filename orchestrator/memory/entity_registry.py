"""Entity registry — populate turn_history / entity_registry / coreference_map for real.

Extracts region/label/bbox from planner + task_output + query, so coreference_resolver
can actually resolve 'that water body' without relying solely on conversation.py bbox append.
"""
from __future__ import annotations
import re
from typing import Any, Dict


def extract_entities(query: str, task_output: Dict[str, Any] | None, plan: Dict[str, Any] | None) -> Dict[str, str]:
    """Return alias -> resolution map. Source-tagged, scoped to session, with timestamps."""
    import time as _t
    reg: Dict[str, str] = {}
    ts = _t.time()
    if task_output:
        bbox = task_output.get("bbox_xyxy") or task_output.get("bbox_normalized") or task_output.get("bbox")
        label = task_output.get("detected_label") or (task_output.get("metadata", {}).get("label") if isinstance(task_output.get("metadata"), dict) else None)
        label = (label or "target").lower()
        if bbox:
            reg[f"that {label}"] = f"bbox:{bbox}|ts:{ts:.0f}"
            reg[f"the {label}"] = f"bbox:{bbox}|ts:{ts:.0f}"
            reg["that area"] = f"bbox:{bbox}|ts:{ts:.0f}"
            reg["that water body"] = f"bbox:{bbox}|ts:{ts:.0f}" if "water" in label else f"bbox:{bbox}|ts:{ts:.0f}"
        # temporal pair
        for k in ("image_t1_id", "image_t2_id", "optical_image_id", "sar_image_id", "image_id"):
            if task_output.get(k):
                reg[k] = str(task_output[k])
        region = task_output.get("region_of_interest") or (plan.get("region_of_interest") if plan else None)
        if isinstance(region, dict) and region.get("region"):
            reg[region["region"].lower()] = f"region:{region}|ts:{ts:.0f}"
        # CRS
        if task_output.get("crs"):
            reg["that crs"] = str(task_output["crs"])
    try:
        from orchestrator.services.geocoder import resolve_from_query
        rg = resolve_from_query(query) if query else None
        if rg and rg.get("region"):
            reg[rg["region"].lower()] = f"region:{rg}|ts:{ts:.0f}"
    except Exception:
        pass
    # pronouns
    if query:
        ql = query.lower()
        if any(p in ql for p in ("that ", "this ", "it ")) and bbox:
            reg["it"] = f"bbox:{bbox}|ts:{ts:.0f}"
    return reg


def build_turn(history_entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "query": history_entry.get("query", ""),
        "task_type": history_entry.get("task_type", ""),
        "answer_text": (history_entry.get("task_output") or {}).get("answer_text", "")[:200],
        "bbox": (history_entry.get("task_output") or {}).get("bbox_xyxy"),
        "timestamp": history_entry.get("timestamp"),
    }
