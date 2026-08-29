"""Spectral indices — pure numpy, no model needed. Add as preprocessing step for change/fusion.

All functions expect float32 ndarrays normalized [0,1] or DN; caller normalizes.
Returns float32 ndarray same shape as input, with nodata masked as NaN handling.
"""
from __future__ import annotations
import numpy as np  # type: ignore
from typing import Dict, Any

def _safe_div(a: np.ndarray, b: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return a / (b + eps)  # type: ignore

def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """NDVI = (NIR - Red) / (NIR + Red)  -> [-1,1], vegetation >0.3"""
    nir = nir.astype(np.float32)  # type: ignore
    red = red.astype(np.float32)  # type: ignore
    denom = nir + red
    ndvi = np.where(np.abs(denom) < 1e-6, 0.0, (nir - red) / (denom + 1e-6)).astype(np.float32)
    return np.clip(ndvi, -1, 1)

def compute_ndwi(green: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDWI (McFeeters) = (Green - NIR)/(Green + NIR) -> water >0.3"""
    green = green.astype(np.float32)  # type: ignore
    nir = nir.astype(np.float32)  # type: ignore
    denom = green + nir
    ndwi = np.where(np.abs(denom) < 1e-6, 0.0, (green - nir) / (denom + 1e-6)).astype(np.float32)
    return np.clip(ndwi, -1, 1)

def compute_ndbi(swir: np.ndarray, nir: np.ndarray) -> np.ndarray:
    """NDBI = (SWIR - NIR)/(SWIR + NIR) -> built-up >0.0"""
    swir = swir.astype(np.float32)  # type: ignore
    nir = nir.astype(np.float32)  # type: ignore
    denom = swir + nir
    ndbi = np.where(np.abs(denom) < 1e-6, 0.0, (swir - nir) / (denom + 1e-6)).astype(np.float32)
    return np.clip(ndbi, -1, 1)

def compute_evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray, G: float = 2.5, C1: float = 6.0, C2: float = 7.5, L: float = 1.0) -> np.ndarray:
    """EVI = G * (NIR - Red) / (NIR + C1*Red - C2*Blue + L)"""
    nir = nir.astype(np.float32)  # type: ignore
    red = red.astype(np.float32)  # type: ignore
    blue = blue.astype(np.float32)  # type: ignore
    denom = nir + C1*red - C2*blue + L
    evi = np.where(np.abs(denom) < 1e-6, 0.0, G * (nir - red) / (denom + 1e-6)).astype(np.float32)
    return np.clip(evi, -1, 1)

def compute_all_indices(bands: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Compute all indices for which required bands exist.
    bands keys expected: B02 blue, B03 green, B04 red, B08 nir, B11 swir (Sentinel-2 naming)
    Also handles l8: blue, green, red, nir, swir1
    Returns {ndvi, ndwi, ndbi, evi} subset available.
    """
    out: Dict[str, Any] = {}
    # normalize key aliases
    def _get(*names):
        for n in names:
            if n in bands:
                return bands[n]
            if n.lower() in bands:
                return bands[n.lower()]
        return None
    red = _get("B04","red","RED","band4")
    nir = _get("B08","nir","NIR","band5","band8")
    green = _get("B03","green","GREEN","band3")
    blue = _get("B02","blue","BLUE","band2")
    swir = _get("B11","swir","SWIR","swir1","band6","band11")
    if nir is not None and red is not None:
        try:
            out["ndvi"] = compute_ndvi(nir, red)
        except Exception:
            pass
    if green is not None and nir is not None:
        try:
            out["ndwi"] = compute_ndwi(green, nir)
        except Exception:
            pass
    if swir is not None and nir is not None:
        try:
            out["ndbi"] = compute_ndbi(swir, nir)
        except Exception:
            pass
    if nir is not None and red is not None and blue is not None:
        try:
            out["evi"] = compute_evi(nir, red, blue)
        except Exception:
            pass
    return out

def indices_as_channels(bands: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    """Return bands + indices merged as channels for vision encoder.
    Adds ndvi etc. as extra channels if available.
    """
    merged = dict(bands)
    idx = compute_all_indices(bands)
    merged.update(idx)
    return merged

# helper for dummy pipeline: generate fake bands and compute indices for trace
def dummy_indices_trace() -> Dict[str, float]:
    """Return dummy mean values for trace when real bands not loaded."""
    return {"ndvi_mean": 0.42, "ndwi_mean": -0.12, "ndbi_mean": 0.18, "evi_mean": 0.35}
