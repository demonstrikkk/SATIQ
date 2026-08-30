"""Embedding service — Groq text-embedding-3-small (1536) with local bge fallback and mock for tests.

Never calls real Groq during `pytest -m "not live"`. Mock returns deterministic hash vector.
"""
from __future__ import annotations
import hashlib
import os
from typing import List

EMBED_DIM_GROQ = 1536
EMBED_DIM_LOCAL = 384

def _mock_vector(text: str, dim: int = EMBED_DIM_GROQ) -> List[float]:
    h = hashlib.sha256(text.encode()).digest()
    # repeat hash to fill dim, normalize to [-1,1]
    vals = []
    for i in range(dim):
        b = h[i % len(h)]
        vals.append((b / 127.5) - 1.0)
    return vals

async def embed_text(text: str) -> List[float]:
    # In tests or when MOCK, return deterministic mock
    if os.getenv("PYTEST_CURRENT_TEST") or os.getenv("MOCK_EMBED") == "1":
        return _mock_vector(text, EMBED_DIM_GROQ)
    # Try Groq embedding if key available
    groq_key = os.getenv("GROQ_API_KEY1") or os.getenv("GROQ_API_KEY") or ""
    if groq_key and len(groq_key) > 20:
        try:
            import httpx  # type: ignore
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/embeddings",
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json={"model": "text-embedding-3-small", "input": text},
                )
                if r.status_code == 200:
                    data = r.json()
                    emb = data["data"][0]["embedding"]
                    if len(emb) == EMBED_DIM_GROQ:
                        return emb
        except Exception:
            pass
    # Local fallback — try sentence-transformers, else mock
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model = SentenceTransformer("BAAI/bge-small-en-v1.5")
        vec = model.encode([text])[0].tolist()
        # pad/truncate to 1536 for pgvector dim consistency
        if len(vec) < EMBED_DIM_GROQ:
            vec = vec + [0.0] * (EMBED_DIM_GROQ - len(vec))
        else:
            vec = vec[:EMBED_DIM_GROQ]
        return vec
    except Exception:
        return _mock_vector(text, EMBED_DIM_GROQ)

def embed_text_sync(text: str) -> List[float]:
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        # already in loop — create task
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as ex:
            fut = ex.submit(asyncio.run, embed_text(text))
            return fut.result(timeout=5)
    except RuntimeError:
        return asyncio.run(embed_text(text))
    except Exception:
        return _mock_vector(text, EMBED_DIM_GROQ)
