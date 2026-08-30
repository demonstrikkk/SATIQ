"""Conversation history + followup detection — SQLite backed for local dev.

Uses orchestrator/storage/memory.db (SQLite) as the single source of truth when
PostgreSQL is not available. This gives the pipeline real chat memory without
an external DB, and survives restarts.
"""
from __future__ import annotations
import json
import os
import sqlite3
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

MEM_HISTORY: Dict[str, List[Dict[str, Any]]] = {}  # fallback cache

def _sqlite_path() -> Path:
    return Path("orchestrator/storage/memory.db")

def _ensure_sqlite():
    p = _sqlite_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        con = sqlite3.connect(str(p))
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                created_at REAL NOT NULL,
                query TEXT,
                task_type TEXT,
                confidence REAL,
                answer_text TEXT,
                result_json TEXT,
                image_ids TEXT
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_conv_session ON conversation_history(session_id, id)")
        con.commit()
        con.close()
    except Exception:
        pass

_ensure_sqlite()

def _history_dir() -> Path:
    return Path("orchestrator/storage/history")

def load_history(session_id: str, n: int = 5) -> List[Dict[str, Any]]:
    # SQLite first — real memory
    try:
        _ensure_sqlite()
        con = sqlite3.connect(str(_sqlite_path()))
        cur = con.cursor()
        cur.execute("SELECT result_json FROM conversation_history WHERE session_id=? ORDER BY id DESC LIMIT ?", (session_id, n))
        rows = cur.fetchall()
        con.close()
        if rows:
            hist = []
            for (j,) in reversed(rows):
                try:
                    hist.append(json.loads(j))
                except Exception:
                    hist.append({"result_json": j})
            return hist[-n:]
    except Exception:
        pass
    # try memory
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
    alt = Path("orchestrator/storage/task_outputs") / f"{session_id}.json"
    if alt.exists():
        try:
            return json.loads(alt.read_text())[-n:]
        except Exception:
            pass
    return []

def save_history(session_id: str, entry: Dict[str, Any]) -> None:
    MEM_HISTORY.setdefault(session_id, []).append(entry)
    # SQLite persist — primary store for chat memory
    try:
        _ensure_sqlite()
        con = sqlite3.connect(str(_sqlite_path()))
        cur = con.cursor()
        import time
        result_json = json.dumps(entry, default=str)
        query = entry.get("query") or entry.get("task_output", {}).get("query") or ""
        task_type = entry.get("task_type") or entry.get("task_output", {}).get("task") or ""
        confidence = entry.get("confidence") or entry.get("task_output", {}).get("confidence")
        answer_text = entry.get("task_output", {}).get("answer_text") or entry.get("answer_text") or ""
        image_ids = ",".join([str(x) for x in (entry.get("image_ids") or [])]) if entry.get("image_ids") else ""
        if not image_ids:
            task_out = entry.get("task_output") or {}
            ids = []
            for k in ["image_id","image_t1_id","image_t2_id","optical_image_id","sar_image_id"]:
                if task_out.get(k):
                    ids.append(task_out[k])
            image_ids = ",".join(ids)
        cur.execute("INSERT INTO conversation_history (session_id, created_at, query, task_type, confidence, answer_text, result_json, image_ids) VALUES (?,?,?,?,?,?,?,?)",
                    (session_id, time.time(), query, task_type, confidence, answer_text[:2000], result_json, image_ids))
        # keep last 50 per session
        cur.execute("DELETE FROM conversation_history WHERE id NOT IN (SELECT id FROM conversation_history WHERE session_id=? ORDER BY id DESC LIMIT 50) AND session_id=?", (session_id, session_id))
        con.commit()
        con.close()
    except Exception:
        pass
    # also disk backup
    hd = _history_dir()
    hd.mkdir(parents=True, exist_ok=True)
    path = hd / f"{session_id}.json"
    try:
        existing = []
        if path.exists():
            existing = json.loads(path.read_text())
        existing.append(entry)
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
