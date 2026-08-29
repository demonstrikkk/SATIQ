"""Conversation history + followup detection.

GraphState gets conversation_history[] and followup_anchor.
History is loaded from PostgreSQL task_outputs fallback to in-memory EXECUTIONS + minio/storage.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

# Try DB, fallback to disk/memory
try:
    from orchestrator.db.session import AsyncSessionLocal  # type: ignore
    from orchestrator.db.models import TaskOutput  # type: ignore
    from sqlalchemy import select  # type: ignore
except Exception:
    AsyncSessionLocal = None  # type: ignore

from orchestrator.services.query_analyzer import detect_followup_intent

MEM_HISTORY: Dict[str, List[Dict[str, Any]]] = {}  # session_id -> list

def _history_dir() -> Path:
    return Path("orchestrator/storage/history")

def load_history(session_id: str, n: int = 5) -> List[Dict[str, Any]]:
    # try memory first
    hist = MEM_HISTORY.get(session_id, [])
    if hist:
        return hist[-n:]
    # try disk
    hd = _history_dir() / f"{session_id}.json"
    if hd.exists():
        try:
            data = json.loads(hd.read_text())
            if isinstance(data, list):
                return data[-n:]
        except Exception:
            pass
    # try minio storage path
    alt = Path("orchestrator/storage/task_outputs") / f"{session_id}.json"
    if alt.exists():
        try:
            return json.loads(alt.read_text())[-n:]
        except Exception:
            pass
    return []

def save_history(session_id: str, entry: Dict[str, Any]) -> None:
    MEM_HISTORY.setdefault(session_id, []).append(entry)
    # also persist to disk
    hd = _history_dir()
    hd.mkdir(parents=True, exist_ok=True)
    path = hd / f"{session_id}.json"
    try:
        existing = []
        if path.exists():
            existing = json.loads(path.read_text())
        existing.append(entry)
        # keep last 20
        existing = existing[-20:]
        path.write_text(json.dumps(existing, indent=2))
    except Exception:
        pass

def detect_followup(query: str, history: List[Dict[str, Any]]) -> Dict[str, Any]:
    return detect_followup_intent(query, history)

def resolve_followup_query(query: str, anchor_task_output: Dict[str, Any]) -> str:
    """Augment followup query with anchor context for router.
    Example: "What about the northern region?" + anchor water body bbox -> "What about the northern region? [previous water body at [0.18,0.09,0.47,0.42]]"
    """
    if not anchor_task_output:
        return query
    # inject anchor image_ids and task_type
    anchor_ids = []
    for k in ["image_id","image_t1_id","image_t2_id","optical_image_id","sar_image_id"]:
        if anchor_task_output.get(k):
            anchor_ids.append(anchor_task_output[k])
    # for grounding, inject bbox
    bbox = anchor_task_output.get("bbox") or anchor_task_output.get("bbox_xyxy") or anchor_task_output.get("bbox_normalized")
    extra_parts = []
    if anchor_ids:
        extra_parts.append(f"[previous image_ids: {','.join(anchor_ids)}]")
    if bbox:
        extra_parts.append(f"[previous bbox: {bbox}]")
    if anchor_task_output.get("task"):
        extra_parts.append(f"[previous task: {anchor_task_output['task']}]")
    if extra_parts:
        return query + " " + " ".join(extra_parts)
    return query

def augment_state_with_history(state: Dict[str, Any]) -> Dict[str, Any]:
    """Called before router: loads history, detects followup, resolves query, injects into state."""
    from orchestrator.models.graph_state import GraphState  # type: ignore
    sid = state.get("session_id", "")
    q = state.get("query","")
    hist = load_history(sid, n=5)
    state["conversation_history"] = hist  # type: ignore
    det = detect_followup(q, hist)
    state["is_followup"] = det["is_followup"]  # type: ignore
    state["followup_anchor"] = det["anchor_task_id"]  # type: ignore
    if det["is_followup"] and hist:
        anchor = hist[-1].get("task_output") or hist[-1]
        resolved = resolve_followup_query(q, anchor)
        # keep original for audit, use resolved for routing
        state["query_original"] = q  # type: ignore
        state["query"] = resolved  # type: ignore
        state["followup_resolved"] = True  # type: ignore
    else:
        state["followup_resolved"] = False  # type: ignore
    return state
