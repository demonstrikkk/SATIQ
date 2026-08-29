"""Dummy fusion — attention/concat/add."""
from __future__ import annotations
from typing import Dict, Any, List
import numpy as np

def run_fusion(embeddings: Dict[str, Any], query: str, method: str = "attention") -> Dict[str, Any]:
    """Fuses embeddings dict into a single repr."""
    # embeddings can be list or dict of lists
    # we produce a deterministic fused vector as mean of all available
    vectors: List[np.ndarray] = []
    if isinstance(embeddings, dict):
        for v in embeddings.values():
            if isinstance(v, list):
                vectors.extend([x for x in v if isinstance(x, np.ndarray)])
            elif isinstance(v, np.ndarray):
                vectors.append(v)
    elif isinstance(embeddings, list):
        vectors = [x for x in embeddings if isinstance(x, np.ndarray)]
    if not vectors:
        fused = np.random.randn(768).astype(np.float32)
    else:
        if method == "attention":
            # weighted mean biased by query length
            w = min(1.0, len(query)/100 + 0.5)
            fused = sum(vectors) / len(vectors) * w
        elif method == "concat":
            # truncated concat
            fused = np.concatenate(vectors)[:768] if len(vectors)>1 else vectors[0][:768]
            if fused.shape[0] < 768:
                fused = np.pad(fused, (0, 768 - fused.shape[0]))
        else:
            fused = sum(vectors) / len(vectors)
    # confidence correlates with method + query length heuristic
    base = 0.82 if method == "attention" else 0.78
    return {
        "fused_repr": fused,  # keep ndarray for downstream, will be serialized as list if needed
        "fusion_method": method,
        "confidence": round(min(0.99, base + (len(query)%10)/100), 3),
        "dim": int(fused.shape[0]),
    }
