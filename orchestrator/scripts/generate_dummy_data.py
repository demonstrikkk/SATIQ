"""Generate fake GeoTIFF + upload to MinIO fallback, create test sessions for 5 task types."""
from __future__ import annotations
import os
import json
import random
import struct
from pathlib import Path

try:
    import numpy as np
    from PIL import Image
except Exception:
    np = None  # type: ignore
    Image = None  # type: ignore

from orchestrator.services.minio_client import minio_client

def _make_array(w=256, h=256, bands=3):
    if np is None:
        return None
    rng = np.random.default_rng(42)
    arr = (rng.random((h,w,bands))*255).astype(np.uint8)
    return arr

def generate_fake_geotiff(path: Path, w=256, h=256, bands=3):
    arr = _make_array(w,h,bands)
    path.parent.mkdir(parents=True, exist_ok=True)
    if arr is not None and Image is not None:
        # Use PNG as stand-in for GeoTIFF (real GeoTIFF needs rasterio/gdal)
        # For true GeoTIFF we try rasterio if available
        try:
            import rasterio
            from rasterio.transform import from_origin
            transform = from_origin(0,0,10,10)
            with rasterio.open(path, 'w', driver='GTiff', height=h, width=w, count=bands, dtype=arr.dtype, crs='EPSG:32617', transform=transform) as dst:
                for i in range(bands):
                    dst.write(arr[:,:,i], i+1)
            print(f"wrote GeoTIFF {path}")
            return path
        except Exception as e:
            print(f"rasterio not available ({e}), writing PNG fallback")
    # PNG fallback
    png_path = path.with_suffix(".png")
    if arr is not None and Image is not None:
        im = Image.fromarray(arr[:,:,0] if bands==1 else arr)
        im.save(png_path)
        print(f"wrote PNG {png_path}")
        return png_path
    # binary fallback
    path.write_bytes(os.urandom(1024))
    print(f"wrote binary stub {path}")
    return path

TEST_CASES = [
    {"task":"vqa", "query":"Describe the land-cover and major objects visible in this image.", "image_id":"img_001"},
    {"task":"grounding", "query":"Locate the water body in the northern sector", "image_id":"img_001"},
    {"task":"change_vqa", "query":"What changed between these two dates, and where?", "image_t1_id":"img_2021","image_t2_id":"img_2023"},
    {"task":"optical_sar_fusion", "query":"Identify built-up and water-covered regions using both images", "optical_image_id":"s2_001","sar_image_id":"s1_001"},
    {"task":"captioning", "query":"Caption this image", "image_id":"img_001"},
]

def main():
    out_dir = Path("orchestrator/storage/rs-raw")
    for tc in TEST_CASES:
        ids = []
        if "image_id" in tc:
            ids.append(tc["image_id"])
        if "image_t1_id" in tc:
            ids.extend([tc["image_t1_id"], tc["image_t2_id"]])
        if "optical_image_id" in tc:
            ids.extend([tc["optical_image_id"], tc["sar_image_id"]])
        for iid in ids:
            p = out_dir / f"{iid}.tif"
            generate_fake_geotiff(p, w=256, h=256, bands=3)
            # upload to minio/fallback
            try:
                data = p.read_bytes() if p.exists() else b"fake"
                minio_client.upload_bytes("rs-raw", f"{iid}.tif", data)
            except Exception as e:
                print(f"upload failed for {iid}: {e}")
        # write test session json
        sess_path = Path("orchestrator/storage/test_sessions") / f"{tc['task']}.json"
        sess_path.parent.mkdir(parents=True, exist_ok=True)
        sess_path.write_text(json.dumps(tc, indent=2))
        print(f"wrote {sess_path}")

if __name__ == "__main__":
    main()
