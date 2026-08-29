"""Synthetic fixtures — no real GeoTIFF needed. Returns numpy arrays + GraphState dicts."""
from __future__ import annotations
import random
import hashlib
from typing import Dict, Any, List

try:
    import numpy as np  # type: ignore
except Exception:
    np = None  # type: ignore

def _fake_tile(shape=(4, 64, 64), sensor="sentinel-2"):
    if np is not None:
        return np.random.randint(0, 255, size=shape, dtype=np.uint8)
    # fallback plain list
    return [[[random.randint(0,255) for _ in range(shape[2])] for _ in range(shape[1])] for _ in range(shape[0])]

def valid_vqa_request():
    """Case 1: Valid single-image VQA — 4-band Sentinel-2 tile."""
    tile = _fake_tile((4,64,64))
    return {
        "query": "How many buildings are visible?",
        "task_type_hint": "vqa",
        "assets": [{"asset_id": "s2_img_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04","B08"], "sensor": "sentinel-2", "bbox": [0,0,256,256]}],
        "image_ids": ["s2_img_001"],
        "_tile": tile,
    }

def valid_change_vqa_request():
    """Case 2: Valid bi-temporal change-VQA — two tiles before/after."""
    t1 = _fake_tile((4,64,64))
    t2 = _fake_tile((4,64,64))
    return {
        "query": "What changed between 2021 and 2023?",
        "task_type_hint": "change_vqa",
        "assets": [
            {"asset_id": "s2_img_2021", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04"], "sensor": "sentinel-2", "acquired_at": "2021-06-01"},
            {"asset_id": "s2_img_2023", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04"], "sensor": "sentinel-2", "acquired_at": "2023-06-01"},
        ],
        "image_ids": ["s2_img_2021","s2_img_2023"],
        "_tiles": (t1,t2),
    }

def malformed_input():
    """Case 3: Malformed — corrupt/truncated bytes."""
    return {
        "query": "How many buildings?",
        "assets": [{"asset_id": "corrupt_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "_corrupt": True, "bands": ["B02"]}],
        "image_ids": ["corrupt_001"],
    }

def unsupported_sensor():
    """Case 4: Unsupported sensor type → encoder compat reject."""
    return {
        "query": "Locate water",
        "assets": [{"asset_id": "weird_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "sensor": "LIDAR-X99", "sensor_type": "LIDAR-X99", "bands": ["B02","B03","B04"]}],
        "image_ids": ["weird_001"],
    }

def coreg_failure_request():
    """Case 5: Co-reg failure — deliberately misaligned tiles (query contains 'mismatch' triggers low SSIM)."""
    return {
        "query": "What changed? mismatch misaligned",
        "assets": [
            {"asset_id": "s2_a", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04"]},
            {"asset_id": "s2_b", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04"]},
        ],
        "image_ids": ["s2_a","s2_b"],
    }

def slow_backend_request(node="vision_encoder"):
    """Case 6: Slow backend — inject NodeTimeoutError via _test_inject."""
    base = valid_vqa_request()
    if node == "vision_encoder":
        base["_test_inject"] = {"vision_slow": True}
    elif node == "fusion":
        base["_test_inject"] = {"fusion_slow": True}
    elif node == "preprocessing":
        base["_test_inject"] = {"preprocessing_slow": True}
    return base

def flaky_backend_request(node="vision_encoder"):
    """Case 7: Flaky — fails first call then succeeds on retry."""
    base = valid_vqa_request()
    if node == "vision_encoder":
        base["_test_inject"] = {"vision_flaky": True}
    elif node == "fusion":
        base["_test_inject"] = {"fusion_flaky": True}
    return base

def repeated_request():
    """Case 8: Same request_key twice — test checkpoint reuse."""
    return valid_vqa_request()

def burst_requests(n=8):
    """Case 9: Burst load — N concurrent requests."""
    base = valid_vqa_request()
    return [dict(base, query=base["query"]+f" #{i}", _idx=i) for i in range(n)]

def circuit_breaker_requests():
    """Case 10: Force consecutive fusion failures past threshold (5)."""
    # create 6 requests that each inject fusion slow so failures accumulate
    return [slow_backend_request("fusion") for _ in range(6)]

def crs_mismatch_request():
    """Extra: CRS mismatch permanent."""
    return {
        "query": "Locate buildings",
        "assets": [
            {"asset_id": "img_1", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0},
            {"asset_id": "img_2", "modality": "optical", "crs": "EPSG:4326", "gsd": 10.0},
        ],
        "image_ids": ["img_1","img_2"],
    }
