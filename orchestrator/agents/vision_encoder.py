"""Agent 8: Vision Encoder — calls dummy encoders."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.dummy.dummy_encoders import run_satmae, run_ssl4eo, run_prithvi, run_croma

def vision_encoder_node(state: GraphState) -> GraphState:
    t0 = time.time()
    encoder = state.get("encoder","satmae")
    tiles = state.get("tiles") or []
    # split by modality for croma
    if encoder == "croma":
        optical_tiles = [t for t in tiles if t.get("modality") in ("optical","multispectral")]
        sar_tiles = [t for t in tiles if t.get("modality")=="sar"]
        # fallback: if not labeled, split by asset_id heuristic
        if not optical_tiles and not sar_tiles and len(tiles)>=2:
            optical_tiles = tiles[:1]
            sar_tiles = tiles[1:]
        elif not optical_tiles and tiles:
            optical_tiles = tiles
            sar_tiles = tiles  # dummy duplicate
        result = run_croma(optical_tiles, sar_tiles)
        embeddings = result
    elif encoder == "prithvi":
        embeddings = {"prithvi": run_prithvi(tiles)}
    elif encoder == "ssl4eo":
        # modality aware
        emb = run_ssl4eo(tiles, modality="optical")
        embeddings = {"ssl4eo": emb}
    else:
        embeddings = {"satmae": run_satmae(tiles)}

    # store as lists (ndarrays); for serialization we keep counts
    state["embeddings"] = {k: {"count": len(v) if isinstance(v, list) else 1, "dim": int(v[0].shape[0]) if isinstance(v, list) and len(v)>0 and hasattr(v[0],"shape") else 768, "_raw": v} for k,v in embeddings.items()} if isinstance(embeddings, dict) else {"default": embeddings}
    # keep raw for fusion (we need actual vectors)
    # store raw separately but not serialized
    state["_embeddings_raw"] = embeddings  # type: ignore
    add_trace(state, "vision_encoder", "ok", {"encoder": encoder, "num_tiles": len(tiles), "embed_keys": list(embeddings.keys()) if isinstance(embeddings, dict) else ["default"]}, latency_ms=int((time.time()-t0)*1000))
    return state
