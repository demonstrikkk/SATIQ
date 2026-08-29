"""Dummy vision encoders — swappable with real SatMAE/SSL4EO/Prithvi/CROMA."""
from __future__ import annotations
import numpy as np
from typing import List, Dict, Any

def _seed_from_id(tile_id: str) -> int:
    return abs(hash(tile_id)) % (2**31)

def run_satmae(tiles: List[Dict[str,Any]], dim: int = 1024) -> List[np.ndarray]:
    """Return fake 1024-d embeddings, deterministic per tile_id for testability."""
    out = []
    for t in tiles:
        tid = t.get("tile_id") or t.get("id") or str(id(t))
        rng = np.random.default_rng(_seed_from_id(tid) % 100000 + 1)
        out.append(rng.standard_normal(dim).astype(np.float32))
    return out

def run_ssl4eo(tiles: List[Dict[str,Any]], modality: str = "optical", dim: int = 768) -> List[np.ndarray]:
    out = []
    for t in tiles:
        tid = t.get("tile_id") or t.get("id") or str(id(t))
        # modality affects seed slightly
        seed = _seed_from_id(tid + modality) % 100000 + 2
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(dim).astype(np.float32)
        # small modality bias to make fused repr non-trivial
        if modality == "sar":
            vec *= 0.9
        out.append(vec)
    return out

def run_prithvi(tiles: List[Dict[str,Any]], dim: int = 768) -> List[np.ndarray]:
    out = []
    for t in tiles:
        tid = t.get("tile_id") or t.get("id") or str(id(t))
        rng = np.random.default_rng(_seed_from_id(tid + "prithvi") % 100000 + 3)
        out.append(rng.standard_normal(dim).astype(np.float32))
    return out

def run_croma(optical_tiles: List[Dict[str,Any]], sar_tiles: List[Dict[str,Any]]) -> Dict[str, Any]:
    """CROMA dummy — returns per-modality embeddings + joint."""
    opt_emb = run_ssl4eo(optical_tiles, modality="optical")
    sar_emb = run_ssl4eo(sar_tiles, modality="sar")
    # joint as average
    joint = [(o + s)/2 for o, s in zip(opt_emb, sar_emb)] if opt_emb and sar_emb else opt_emb or sar_emb
    return {"optical": opt_emb, "sar": sar_emb, "joint": joint, "model": "croma_dummy"}
