"""Request-key checkpointing (§2.6) — in-memory dict, Redis override noted in comment.

Production: replace _STORE with Redis / KV store (key = request_key:stage).
Audit fix: key = sorted image hashes + normalized query + task_type + sar_polarization
"""
from __future__ import annotations
import hashlib
import re
from typing import Any, Dict, Optional

# In-memory store for dummy testing: {request_key: {stage: state_slice}}
_STORE: Dict[str, Dict[str, Any]] = {}

# Stages that are worth checkpointing (expensive deterministic steps)
CHECKPOINT_STAGES = {"preprocessing", "vision_encoder"}

def _normalize_query(q: str) -> str:
    q = (q or "").strip().lower()
    q = re.sub(r"\s+", " ", q)
    return q

def compute_request_key(
    image_ids: list[str] | None,
    query: str | None,
    task_type: str | None,
    sar_polarization: str | None = None,
    assets: list[dict] | None = None,
) -> str:
    """Audit fix: order-independent image hash + normalized query + sar_polarization."""
    ids = sorted([(i or "").strip() for i in (image_ids or []) if i])
    # fall back to asset ids if image_ids empty
    if not ids and assets:
        ids = sorted([(a.get("asset_id") or a.get("id") or "") for a in assets if isinstance(a, dict)])
        ids = [i for i in ids if i]
    # hash each id then sort (defensive even though ids already sorted)
    h_ids = hashlib.sha256("|".join(ids).encode()).hexdigest()[:12] if ids else "noimg"
    h_q = hashlib.sha256(_normalize_query(query or "").encode()).hexdigest()[:12]
    tt = (task_type or "unknown").lower()
    pol = (sar_polarization or "").strip().lower()
    h_pol = hashlib.sha256(pol.encode()).hexdigest()[:6] if pol else "nopol"
    raw = f"{h_ids}:{h_q}:{tt}:{h_pol}"
    # final hash short
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def save_checkpoint(request_key: str, stage: str, payload: Dict[str, Any]):
    if not request_key or stage not in CHECKPOINT_STAGES:
        return
    bucket = _STORE.setdefault(request_key, {})
    # shallow copy to avoid mutation
    bucket[stage] = dict(payload)

def load_checkpoint(request_key: str, stage: str) -> Optional[Dict[str, Any]]:
    if not request_key:
        return None
    bucket = _STORE.get(request_key)
    if not bucket:
        return None
    hit = bucket.get(stage)
    if hit is None:
        return None
    return dict(hit)

def has_checkpoint(request_key: str, stage: str) -> bool:
    return load_checkpoint(request_key, stage) is not None

def clear_checkpoint(request_key: str):
    _STORE.pop(request_key, None)

def hit_count(request_key: str) -> int:
    return len(_STORE.get(request_key, {}))

def reset_store():
    _STORE.clear()
