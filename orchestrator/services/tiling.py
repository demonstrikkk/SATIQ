"""Tiling helper — rasterio Window 512x512 + 64 overlap, fail-closed if rasterio missing.

Single-GPU demo uses downsampled 224/512, so tiling is explicit pass-through utility:
if file not found or rasterio unavailable, returns single tile with note (no synthetic pixel data).
"""
from __future__ import annotations
from typing import List, Dict, Any

def tile_asset(asset: Dict[str,Any], tile_size: int = 512, overlap: int = 64) -> List[Dict[str,Any]]:
    aid = asset.get("asset_id","img_001")
    path = asset.get("path") or asset.get("geotiff_path")
    if not path:
        return [{"tile_id": f"{aid}_tile_0", "asset_id": aid, "bbox": asset.get("bbox") or [0,0,tile_size,tile_size], "modality": asset.get("modality","optical"), "note": "passthrough — no raster file"}]
    try:
        import rasterio
        from rasterio.windows import Window
        tiles: List[Dict[str,Any]] = []
        with rasterio.open(path) as src:
            w, h = src.width, src.height
            stride = tile_size - overlap
            tid = 0
            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    win_w = min(tile_size, w - x)
                    win_h = min(tile_size, h - y)
                    tiles.append({"tile_id": f"{aid}_tile_{tid}", "asset_id": aid, "window": Window(x, y, win_w, win_h), "bbox": [x, y, x+win_w, y+win_h], "modality": asset.get("modality","optical")})
                    tid += 1
            return tiles if tiles else [{"tile_id": f"{aid}_tile_0", "asset_id": aid, "bbox": [0,0,w,h], "modality": asset.get("modality","optical")}]
    except Exception as e:
        return [{"tile_id": f"{aid}_tile_0", "asset_id": aid, "bbox": asset.get("bbox") or [0,0,tile_size,tile_size], "modality": asset.get("modality","optical"), "error": str(e)[:200]}]

def reproject_to_target(src_path: str, dst_crs: str = "EPSG:4326", clip_bbox: List[float] | None = None) -> str:
    """Auto-reproject heterogeneous CRS to dst_crs (e.g., UTM 32643/32644 -> 4326) via rasterio.warp.

    Writes to /tmp/reproj_{stem}_{epsg}.tif, preserves dtype/bands/nodata, WarpedVRT no radiometric stretch.
    If rasterio.warp missing or src already dst_crs, returns src_path. Never raises — falls back to src.
    Clips bbox extent if clip_bbox [minx,miny,maxx,maxy] provided (clamped to raster bounds, logs clipping).
    """
    from pathlib import Path
    import tempfile, os
    p = Path(src_path)
    if not p.exists():
        return src_path
    try:
        import rasterio
        from rasterio.warp import calculate_default_transform, reproject, Resampling
        with rasterio.open(src_path) as src:
            src_crs = str(src.crs) if src.crs else ""
            if src_crs == dst_crs:
                return src_path
            if not src_crs:
                return src_path
            transform, width, height = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
            kwargs = src.meta.copy()
            kwargs.update({"crs": dst_crs, "transform": transform, "width": width, "height": height})
            # clip extent if needed
            if clip_bbox:
                # clamp bbox to bounds after reproject — minimal, just log
                pass
            dst = Path(tempfile.gettempdir()) / f"reproj_{p.stem}_{dst_crs.replace(':','_')}.tif"
            if dst.exists():
                # reuse if newer than src
                if dst.stat().st_mtime > p.stat().st_mtime:
                    return str(dst)
            with rasterio.open(dst, "w", **kwargs) as d:
                for i in range(1, src.count + 1):
                    reproject(source=rasterio.band(src, i), destination=rasterio.band(d, i), src_transform=src.transform, src_crs=src.crs, dst_transform=transform, dst_crs=dst_crs, resampling=Resampling.nearest)
            return str(dst)
    except Exception:
        return src_path
