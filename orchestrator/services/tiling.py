"""Tiling helper — dummy for now, rasterio when GeoTIFF available."""
from __future__ import annotations
from typing import List, Dict, Any

def tile_asset(asset: Dict[str,Any], tile_size: int = 256) -> List[Dict[str,Any]]:
    """Split asset into tiles (dummy: 1 tile). Real would use rasterio."""
    # if rasterio + file exists, we would open and window; for now dummy
    aid = asset.get("asset_id","img_001")
    return [{"tile_id": f"{aid}_tile_0", "asset_id": aid, "bbox": asset.get("bbox") or [0,0,tile_size,tile_size], "modality": asset.get("modality","optical")}]
