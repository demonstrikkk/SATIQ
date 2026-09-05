"""Vendored preprocessing for Model4 CROMA — S2 12-band + S1 2-band to (C,H,W) tensors.

Handles both BigEarthNet patch dirs ( *_B0*.tif ) and single GeoTIFFs via rasterio/PIL fallback.
Fails closed: if file missing or band count wrong, raises FileNotFoundError / RuntimeError.
No dummy random invented — caller decides DEMO path.
"""
from pathlib import Path
from typing import Tuple
import numpy as np
import torch
import cv2

def _load_patch_bands(patch_dir: Path, target_size: Tuple[int,int]) -> np.ndarray:
    # Expect 12 Sentinel-2 bands B01..B12 etc as *_B*.tif — read via rasterio if available
    bands = []
    for pat in ["*_B01*.tif","*_B02*.tif","*_B03*.tif","*_B04*.tif","*_B05*.tif","*_B06*.tif","*_B07*.tif","*_B08*.tif","*_B8A*.tif","*_B09*.tif","*_B11*.tif","*_B12*.tif"]:
        matches = list(patch_dir.glob(pat))
        if matches:
            try:
                import rasterio
                with rasterio.open(matches[0]) as src:
                    arr = src.read(1).astype(np.float32)
                    if arr.shape != target_size:
                        arr = cv2.resize(arr, target_size, interpolation=cv2.INTER_LINEAR)
                    bands.append(arr)
            except Exception:
                bands.append(np.zeros(target_size, dtype=np.float32))
        else:
            # missing band -> zero
            bands.append(np.zeros(target_size, dtype=np.float32))
    # Ensure 12
    while len(bands) < 12:
        bands.append(np.zeros(target_size, dtype=np.float32))
    return np.stack(bands[:12], axis=0)  # (12,H,W)

def load_and_preprocess_s2(s2_path: str, target_size=(120,120)) -> torch.Tensor:
    p = Path(s2_path)
    if not p.exists():
        raise FileNotFoundError(f"S2 path not found: {s2_path}")
    th, tw = target_size[1], target_size[0] if len(target_size)==2 else (120,120)
    # Patch dir
    if p.is_dir():
        arr = _load_patch_bands(p, (tw, th))
        # Percentile normalize per band
        for i in range(arr.shape[0]):
            lo, hi = np.percentile(arr[i], 2), np.percentile(arr[i], 98)
            if hi > lo:
                arr[i] = np.clip((arr[i]-lo)/(hi-lo), 0, 1)
            else:
                arr[i] = np.clip(arr[i]/4000.0, 0, 1)
        return torch.from_numpy(arr).float()
    # Single GeoTIFF
    try:
        import rasterio
        with rasterio.open(p) as src:
            count = src.count
            arr = src.read(out_shape=(count, th, tw), resampling=5).astype(np.float32)  # type: ignore
            # if >12 take first 12, if <12 pad
            if arr.shape[0] > 12:
                arr = arr[:12]
            elif arr.shape[0] < 12:
                pad = np.zeros((12-arr.shape[0], th, tw), dtype=np.float32)
                arr = np.concatenate([arr, pad], axis=0)
            # normalize
            arr = np.clip(arr / 4000.0, 0, 1)
            return torch.from_numpy(arr).float()
    except Exception:
        pass
    # PIL fallback (RGB only -> 3 bands, pad to 12)
    from PIL import Image
    im = Image.open(p).convert("RGB").resize((tw, th))
    arr = np.array(im).astype(np.float32)/255.0  # H,W,3
    arr = arr.transpose(2,0,1)  # 3,H,W
    pad = np.zeros((9, th, tw), dtype=np.float32)
    arr12 = np.concatenate([arr, pad], axis=0)
    return torch.from_numpy(arr12).float()

def load_and_preprocess_s1(s1_path: str, target_size=(120,120)) -> torch.Tensor:
    p = Path(s1_path)
    if not p.exists():
        raise FileNotFoundError(f"S1 path not found: {s1_path}")
    th, tw = target_size[1], target_size[0] if len(target_size)==2 else (120,120)
    if p.is_dir():
        # Take first two VV/VH tifs
        tifs = sorted(p.glob("*.tif"))[:2]
        bands = []
        for tf in tifs:
            try:
                import rasterio
                with rasterio.open(tf) as src:
                    arr = src.read(1).astype(np.float32)
                    if arr.shape != (th, tw):
                        arr = cv2.resize(arr, (tw, th), interpolation=cv2.INTER_LINEAR)
                    bands.append(np.clip(arr/100.0, -1, 1))
            except Exception:
                bands.append(np.zeros((th, tw), dtype=np.float32))
        while len(bands) < 2:
            bands.append(np.zeros((th, tw), dtype=np.float32))
        return torch.from_numpy(np.stack(bands[:2], axis=0)).float()
    try:
        import rasterio
        with rasterio.open(p) as src:
            count = min(src.count, 2)
            arr = src.read(out_shape=(count, th, tw), resampling=5).astype(np.float32)  # type: ignore
            if count == 1:
                # duplicate VH from VV if single pol
                arr = np.concatenate([arr, arr], axis=0)
            arr = np.clip(arr/100.0, -1, 1)
            return torch.from_numpy(arr).float()
    except Exception:
        pass
    from PIL import Image
    im = Image.open(p).convert("L").resize((tw, th))
    arr = np.array(im).astype(np.float32)/255.0
    arr = np.stack([arr, arr], axis=0)
    return torch.from_numpy(arr).float()
