"""Agent 11: Tile Manager — Redis-backed lifecycle."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace

# In real system would update Redis hash session:{sid}:tiles
# Here we update state and simulate

def tile_manager_node(state: GraphState) -> GraphState:
    t0 = time.time()
    tiles = state.get("tiles") or []
    # mark all as done after encoding
    for t in tiles:
        t["status"] = "done"
        t["updated_at"] = time.time()
    # also track in trace
    counts = {"pending": 0, "done": 0, "failed": 0}
    for t in tiles:
        s = t.get("status","pending")
        counts[s] = counts.get(s, 0) + 1
    # if we had Redis, we'd hset here; we simulate via state
    state["tiles"] = tiles
    add_trace(state, "tile_manager", "ok", {"counts": counts, "num_tiles": len(tiles)}, latency_ms=int((time.time()-t0)*1000))
    return state
