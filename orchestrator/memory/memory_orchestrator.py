"""Memory orchestrator — 4-tier Satiq memory per ADR 0009 research.

Tiers (per 2026 reference architecture, constrained for 45s single-GPU):
  1. Working  — last 3 turns + entity_registry, always in-context, <1k tokens
  2. Episodic  — append-only turn docs in Chroma satiq_episodic (TTL 90d), hybrid vector+BM25+recency
  3. Semantic  — distilled facts (AOI, sensor, failure) in Chroma satiq_semantic, provenance-tracked, TTL 180d
  4. State     — Redis EXECUTIONS + gateway assetStore, TTL 1h, authoritative live

Write path: episodic always, semantic only via consolidation (not per-turn direct writes).
Read path: working → episodic hybrid (top_k 6, threshold 0.72, time-decay) → semantic → state
"""
from __future__ import annotations
import time
from typing import Any, Dict, List

from orchestrator.core.config import get_settings

# ---- Working ----
def build_working_context(history: List[Dict[str, Any]], entity_registry: Dict[str, str] | None, max_turns: int = 3) -> str:
    turns = history[-max_turns:] if history else []
    lines: List[str] = []
    for h in turns:
        q = (h.get("query") or "")[:160]
        ans = (h.get("answer_text") or (h.get("task_output") or {}).get("answer_text") or "")[:160]
        tid = h.get("task_type") or ""
        lines.append(f"- Q({tid}): {q} -> A: {ans}")
    if entity_registry:
        lines.append(f"ENTITIES: {entity_registry}")
    return "\n".join(lines)[:900]

# ---- Episodic retrieve (vector + BM25 + time-decay) ----
async def retrieve_episodic(query: str, session_id: str, top_k: int | None = None) -> List[Dict[str, Any]]:
    from orchestrator.memory.rag_store import retrieve as rag_retrieve
    s = get_settings()
    k = top_k or int(getattr(s, "rag_top_k", 6))
    hits = await rag_retrieve(query, session_id, top_k=k)
    # time-decay boost: exp(-age_hours / 168) (1 week half-life) — rag_store already does session boost
    now = time.time()
    for h in hits:
        ts = h.get("metadata", {}).get("ts") or h.get("metadata", {}).get("created_at") or now
        try:
            age_h = max(0, (now - float(ts)) / 3600)
            decay = pow(0.5, age_h / 168.0)
            h["score"] = float(h.get("similarity", 0)) * (0.7 + 0.3 * decay)
        except Exception:
            h["score"] = float(h.get("similarity", 0))
    hits.sort(key=lambda x: x.get("score", 0), reverse=True)
    return hits[:k]

# ---- Semantic (distilled facts) ----
def extract_semantic_fact(query: str, task_output: Dict[str, Any] | None, plan: Dict[str, Any] | None) -> Dict[str, Any] | None:
    """Rule-based semantic extraction — no LLM, <1ms. Returns fact or None."""
    if not query and not task_output:
        return None
    fact: Dict[str, Any] = {}
    # AOI / region
    try:
        from orchestrator.services.geocoder import resolve_from_query
        rg = resolve_from_query(query) if query else None
        if rg and rg.get("region"):
            fact["aoi"] = rg["region"]
    except Exception:
        pass
    # sensor hint
    ql = (query or "").lower()
    if "sar" in ql or "s1" in ql:
        fact["sensor"] = "SAR"
    elif "optical" in ql or "sentinel-2" in ql or "s2" in ql:
        fact["sensor"] = "Optical"
    if task_output:
        if task_output.get("bbox_xyxy") or task_output.get("bbox_normalized"):
            fact["has_bbox"] = True
        if task_output.get("crs"):
            fact["crs"] = task_output["crs"]
        if task_output.get("task") == "change_vqa":
            fact["temporal"] = True
    if not fact:
        return None
    return {"fact": fact, "provenance": query[:120], "ts": time.time(), "confidence": 0.75}

async def store_semantic(session_id: str, fact: Dict[str, Any]):
    try:
        from orchestrator.memory.rag_store import add_semantic
        await add_semantic(session_id, fact)
    except Exception:
        pass

# ---- Orchestrated retrieve for planner ----
async def retrieve_for_planner(query: str, session_id: str) -> Dict[str, Any]:
    """Returns {working, episodic_hits, semantic_hits, combined_text} for planner prompt augmentation."""
    from orchestrator.services.conversation import load_history
    hist = load_history(session_id, n=5)
    try:
        from orchestrator.services.conversation import MEM_HISTORY
        # entity registry from last turn
        entity_reg = {}
        if hist and hist[-1].get("task_output"):
            from orchestrator.memory.entity_registry import extract_entities
            entity_reg = extract_entities(hist[-1].get("query",""), hist[-1].get("task_output"), None)
    except Exception:
        entity_reg = {}
    working = build_working_context(hist, entity_reg)
    episodic = await retrieve_episodic(query, session_id)
    # semantic
    semantic: List[Dict[str, Any]] = []
    try:
        from orchestrator.memory.rag_store import retrieve_semantic
        semantic = await retrieve_semantic(query, session_id, top_k=3)
    except Exception:
        semantic = []
    combined_parts = [working]
    for h in episodic[:3]:
        combined_parts.append(f"[EPISODIC sim={h.get('similarity',0):.2f}] {h.get('document','')[:180]}")
    for h in semantic[:2]:
        combined_parts.append(f"[SEMANTIC] {h.get('document','')[:160]}")
    return {"working": working, "episodic": episodic, "semantic": semantic, "combined_text": "\n".join(combined_parts)[:1200], "history": hist}

# ---- Consolidation (background, TTL-aware) ----
def should_consolidate(history: List[Dict[str, Any]]) -> bool:
    # consolidate every 4 turns or when same AOI repeats 2x
    if len(history) < 3:
        return False
    if len(history) % 4 == 0:
        return True
    # AOI repeat
    aois = []
    for h in history[-4:]:
        q = (h.get("query") or "").lower()
        if "karnataka" in q or "sector" in q or "coastal" in q:
            aois.append(q)
    return len(set(aois)) < len(aois)

async def consolidate(session_id: str):
    from orchestrator.services.conversation import load_history
    hist = load_history(session_id, n=10)
    if not should_consolidate(hist):
        return
    # extract and store one semantic fact from last turn
    last = hist[-1] if hist else {}
    fact = extract_semantic_fact(last.get("query",""), last.get("task_output"), None)
    if fact:
        await store_semantic(session_id, fact)
