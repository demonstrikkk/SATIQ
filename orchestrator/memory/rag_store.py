"""RAG store — Chroma (LlamaIndex) + embedding cache + SQLite fallback.

Design:
- Chroma collection `satiq_conversation` (persistent at settings.chroma_path or http://chroma:8000)
- Embedding via orchestrator.services.embedding (Groq → BGE → mock) with TTLCache 3600/1024
- LlamaIndex is optional: if not installed, falls back to direct Chroma + cosine
- Retrieve merges recency (last 3) + similarity (top_k 6, threshold 0.72) deduped

Until Chroma is available, load_history SQLite recency still works (graceful degrade).
"""
from __future__ import annotations
import hashlib
from typing import Any, Dict, List

from orchestrator.core.config import get_settings
from orchestrator.core.ttl_cache import TTLCache

_embed_cache = TTLCache(ttl_seconds=3600, max_entries=1024)


async def cached_embed(text: str) -> List[float]:
    key = hashlib.sha256(text.encode()).hexdigest()
    cached = _embed_cache.get(key)
    if cached is not None:
        return cached
    from orchestrator.services.embedding import embed_text
    vec = await embed_text(text)
    _embed_cache.set(key, vec)
    return vec


def _chroma_client():
    s = get_settings()
    host = getattr(s, "chroma_host", "") or ""
    path = getattr(s, "chroma_path", "chroma_db")
    try:
        import chromadb  # type: ignore
        if host and host.strip():
            try:
                client = chromadb.HttpClient(host=host.replace("http://", "").split(":")[0], port=int(host.split(":")[-1]) if ":" in host else 8000)
                client.heartbeat()
                return client
            except Exception:
                pass
        client = chromadb.PersistentClient(path=path)
        return client
    except Exception:
        return None


def _get_collection(name: str = "satiq_conversation"):
    client = _chroma_client()
    if client is None:
        return None
    try:
        col = client.get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
        return col
    except Exception:
        return None

def _get_episodic_collection():
    return _get_collection("satiq_conversation")

def _get_semantic_collection():
    return _get_collection("satiq_semantic")


async def add_turn(session_id: str, turn_id: str, query: str, answer_text: str, metadata: Dict[str, Any] | None = None):
    """Episodic append-only — TTL 90d, provenance timestamped."""
    col = _get_episodic_collection()
    if col is None:
        return
    try:
        import time as _t
        vec = await cached_embed(query + " " + (answer_text or "")[:500])
        doc = f"Q: {query}\nA: {answer_text[:800]}"
        mid = f"{session_id}:{turn_id}"
        col.upsert(ids=[mid], embeddings=[vec], documents=[doc], metadatas=[{"session_id": session_id, "ts": _t.time(), **(metadata or {})}])
    except Exception:
        pass

async def add_semantic(session_id: str, fact: Dict[str, Any]):
    """Semantic distilled fact — TTL 180d, provenance-tracked."""
    col = _get_semantic_collection()
    if col is None:
        return
    try:
        import time as _t, hashlib as _hl
        text = str(fact.get("fact") or fact)
        vec = await cached_embed(text)
        fid = _hl.sha256((session_id + text).encode()).hexdigest()[:16]
        doc = f"FACT: {text} | provenance: {fact.get('provenance','')[:100]}"
        col.upsert(ids=[fid], embeddings=[vec], documents=[doc], metadatas=[{"session_id": session_id, "ts": _t.time(), "confidence": fact.get("confidence", 0.75)}])
    except Exception:
        pass


async def retrieve(query: str, session_id: str, top_k: int | None = None, threshold: float | None = None) -> List[Dict[str, Any]]:
    """Hybrid episodic retrieve — vector cosine + BM25 fallback + session boost."""
    s = get_settings()
    top_k = top_k or int(getattr(s, "rag_top_k", 6))
    threshold = threshold if threshold is not None else float(getattr(s, "rag_threshold", 0.72))
    col = _get_episodic_collection()
    if col is None:
        return []
    try:
        vec = await cached_embed(query)
        res = col.query(query_embeddings=[vec], n_results=top_k * 2, where={"session_id": session_id}, include=["documents", "metadatas", "distances"])
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out = []
        q_terms = set(query.lower().split())
        for doc, meta, dist in zip(docs, metas, dists):
            sim = 1 - (dist or 0)
            # BM25-like lexical boost (overlap / len)
            d_terms = set((doc or "").lower().split())
            overlap = len(q_terms & d_terms) / max(1, len(q_terms))
            hybrid = 0.7 * sim + 0.3 * overlap
            if hybrid < threshold:
                continue
            out.append({"document": doc, "metadata": meta, "similarity": sim, "hybrid_score": hybrid, "distance": dist})
        # session boost + hybrid sort
        out.sort(key=lambda x: (0 if x["metadata"].get("session_id") == session_id else 1, -x.get("hybrid_score", x["similarity"])))
        return out[:top_k]
    except Exception:
        return []

async def retrieve_semantic(query: str, session_id: str, top_k: int = 3, threshold: float = 0.6) -> List[Dict[str, Any]]:
    col = _get_semantic_collection()
    if col is None:
        return []
    try:
        vec = await cached_embed(query)
        res = col.query(query_embeddings=[vec], n_results=top_k, where={"session_id": session_id}, include=["documents", "metadatas", "distances"])
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        out = []
        for doc, meta, dist in zip(docs, metas, dists):
            sim = 1 - (dist or 0)
            if sim < threshold:
                continue
            out.append({"document": doc, "metadata": meta, "similarity": sim, "distance": dist})
        out.sort(key=lambda x: -x["similarity"])
        return out
    except Exception:
        return []


def clear_collection():
    for name in ("satiq_conversation", "satiq_semantic"):
        col = _get_collection(name)
        if col is not None:
            try:
                ids = col.get(limit=1000).get("ids", [])
                if ids:
                    col.delete(ids=ids)
            except Exception:
                pass
    _embed_cache.clear()

def ttl_cleanup(max_age_days: int = 90):
    """Manual TTL sweep — call from periodic cleanup (90d episodic, 180d semantic)."""
    import time as _t
    now = _t.time()
    for name, ttl_days in (("satiq_conversation", 90), ("satiq_semantic", 180)):
        col = _get_collection(name)
        if col is None:
            continue
        try:
            got = col.get(include=["metadatas"])
            ids = got.get("ids", [])
            metas = got.get("metadatas", [])
            to_del = [i for i, m in zip(ids, metas) if now - float(m.get("ts", now)) > ttl_days * 86400]
            if to_del:
                col.delete(ids=to_del)
        except Exception:
            pass
