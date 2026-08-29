"""Agent 6: Data & Preprocessing — tiling + dummy co-reg."""
from __future__ import annotations
import time
import random
from orchestrator.models.graph_state import GraphState, add_trace

def preprocessing_node(state: GraphState) -> GraphState:
    t0 = time.time()
    assets = state.get("assets") or []
    image_ids = state.get("image_ids") or []
    task_type = state.get("task_type","vqa")
    plan = state.get("plan") or {}
    # region_of_interest from planner/geocoder: filter tiles to ROI bbox if present
    roi = state.get("region_of_interest") or plan.get("region_of_interest")

    # If no assets but image_ids, synthesize minimal assets
    if not assets and image_ids:
        assets = [{"asset_id": iid, "modality": "optical", "crs": "EPSG:4326", "gsd": 10.0} for iid in image_ids]
        state["assets"] = assets
    if not assets and not image_ids:
        # synthetic single asset for text-only testing
        assets = [{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bbox": [0,0,512,512]}]
        state["assets"] = assets
        # fill image_ids for downstream
        state["image_ids"] = ["img_001"]

    # tiling: create 1-4 tiles per image (dummy)
    tiles = []
    for asset in assets:
        aid = asset.get("asset_id") or asset.get("id") or "img_001"
        # for multispectral or large, could be 4 tiles; keep 1 for speed
        num_tiles = 1
        if task_type in ("change_vqa","optical_sar_fusion"):
            num_tiles = 2
        for i in range(num_tiles):
            tiles.append({
                "tile_id": f"{aid}_tile_{i}",
                "asset_id": aid,
                "bbox": asset.get("bbox") or [0,0,256,256],
                "modality": asset.get("modality","optical"),
                "status": "pending",
            })

    # ROI filtering: if region bbox present, keep only tiles intersecting ROI (dummy: keep all but tag)
    if roi and roi.get("bbox"):
        roi_bbox = roi["bbox"]
        # for dummy tiles with bbox [0,0,256,256], we just tag which tiles are inside ROI
        for t in tiles:
            t["roi"] = roi["region"]
            t["roi_bbox"] = roi_bbox
        state["roi_filtered"] = True  # type: ignore
    state["tiles"] = tiles

    # Spectral indices as preprocessing step for change/fusion (zero cost, numpy only)
    spectral_trace = {}
    if task_type in ("change_vqa","optical_sar_fusion"):
        try:
            from orchestrator.services.spectral import dummy_indices_trace, compute_all_indices
            # try real bands if assets carry band arrays (not in dummy, so use dummy)
            has_bands = any(a.get("bands") for a in assets)
            if has_bands:
                # real: build bands dict and compute
                spectral_trace = dummy_indices_trace()
            else:
                spectral_trace = dummy_indices_trace()
            state["spectral_indices"] = spectral_trace  # type: ignore
        except Exception as e:
            spectral_trace = {"error": str(e)[:200]}
            state["spectral_indices"] = spectral_trace  # type: ignore

    # dummy co-registration quality metrics
    rnd = random.Random(abs(hash(state.get("session_id","")) ) % 100000)
    if len(assets) >= 2:
        # ssim 0.85-0.95 for good, occasional low to trigger gate
        ssim = round(0.88 + rnd.random()*0.07, 3)
        residual = round(rnd.random()*0.4, 3)
        # if query contains "mismatch" force low ssim for testing gate
        if "mismatch" in (state.get("query") or "").lower():
            ssim = 0.62
            residual = 0.85
    else:
        ssim = 1.0
        residual = 0.0

    coreg = {
        "ssim": ssim,
        "residual": residual,
        "method": "dummy_affine",
        "passed": ssim >= 0.75 and residual <= 0.6,
        "num_tiles": len(tiles),
    }
    state["coreg"] = coreg
    state["preprocessing_done"] = True
    # tile creation side-effect: also stage in tile_manager state (persistent)
    # tile_manager will later poll stitch_ready
    state.setdefault("tile_ids", [t["tile_id"] for t in tiles])  # type: ignore

    add_trace(state, "preprocessing", "ok", {"num_tiles": len(tiles), "coreg": coreg, "gsd_normalized": 10.0, "spectral": spectral_trace, "roi": roi}, latency_ms=int((time.time()-t0)*1000))
    return state
