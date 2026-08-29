"""Dummy task agents — 4 models matching prompt spec exactly."""
from __future__ import annotations
import random
from typing import Dict, Any, List

# keep deterministic by query hash for testing
def _seed(query: str) -> int:
    return abs(hash(query)) % (2**31)

def dummy_vqa(fused_repr, query: str, image_id: str = "img_001") -> Dict[str, Any]:
    """Model 1 — VQA open/closed."""
    ql = query.lower()
    is_closed = any(k in ql for k in ["how many", "count", "is there", "yes", "no", "number"])
    if "count" in ql or "how many" in ql:
        answer_text = "There are 3 built-up clusters visible in the eastern sector."
        answer_type = "closed"
        answer_short = "3"
        numeric = 3.0
        unit = "count"
    elif "is there" in ql or ql.startswith("is ") or ql.startswith("are "):
        answer_text = "Yes, water is present along the northern edge."
        answer_type = "closed"
        answer_short = "yes"
        numeric = 1.0
        unit = "count"
    else:
        answer_text = "The image shows a mix of agricultural fields in the center, a small settlement cluster to the east, and a forested patch along the western edge."
        answer_type = "open"
        answer_short = None
        numeric = None
        unit = None
    # confidence 0.8-0.9
    rnd = random.Random(_seed(query))
    conf = round(0.78 + rnd.random()*0.12, 2)
    # per-tile confidence and attention for model_interface
    per_tile = {f"{image_id}_tile_0": round(0.86 + rnd.random()*0.08,3)}
    return {
        "task": "vqa",
        "query": query,
        "image_id": image_id,
        "answer_text": answer_text,
        "answer_type": answer_type,
        "answer_short": answer_short,
        "confidence": conf,
        "spatial_bbox": None,
        "answer_numeric": numeric,
        "answer_unit": unit,
        "answer_temporal_ref": None,
        "per_tile_confidence": per_tile,
        "attention_maps": None,
        "caption_text": answer_text if "caption" in ql else None,
        "key_objects": ["agricultural fields","settlement","forest"] if answer_type=="open" else [],
    }

def dummy_grounding(fused_repr, query: str, image_id: str = "img_001") -> Dict[str, Any]:
    rnd = random.Random(_seed(query + "ground"))
    # simulate bbox around water/northern sector
    bbox_norm = [0.18, 0.09, 0.47, 0.42]  # x_min, y_min, x_max, y_max normalized
    bbox_xyxy = [120, 45, 310, 210]
    # vary slightly
    jitter = (rnd.random()-0.5)*0.04
    bbox_norm = [round(max(0,min(1, v+jitter)), 3) for v in bbox_norm]
    conf = round(0.82 + rnd.random()*0.08, 2)
    # generate second bbox for multi-detection case if query mentions multiple
    bbox_list = [bbox_xyxy]
    if "multiple" in query.lower() or "all" in query.lower():
        bbox_list = [bbox_xyxy, [310, 210, 420, 320]]
    return {
        "task": "grounding",
        "query": query,
        "image_id": image_id,
        "answer_text": f"Water body detected in the northern sector with confidence {conf:.2f}. BBox (normalized) {bbox_norm} corresponds to xyxy {bbox_xyxy}.",
        "bbox_normalized": bbox_norm,
        "bbox_xyxy": bbox_xyxy,
        "bbox": bbox_norm,
        "bbox_list": bbox_list,
        "phrase_grounding_map": {"water body": [bbox_xyxy]},
        "mask_rle": None,
        "confidence": conf,
        "detections": len(bbox_list),
        "status": "OK",
        "answer_numeric": float(len(bbox_list)),
        "answer_unit": "count",
        "per_tile_confidence": {f"{image_id}_tile_0": conf},
        "attention_maps": None,
    }

def dummy_change_vqa(fused_repr, query: str, image_t1_id: str = "img_2021", image_t2_id: str = "img_2023") -> Dict[str, Any]:
    rnd = random.Random(_seed(query + "change"))
    cats = ["built-up_increase"]
    if "water" in query.lower():
        cats = ["water_increase", "built-up_increase"]
    elif "vegetation" in query.lower() or "forest" in query.lower():
        cats = ["vegetation_decrease"]
    conf = round(0.75 + rnd.random()*0.12, 2)
    # numeric: change magnitude pct and area
    magnitude = round(12.5 + rnd.random()*8, 2)  # percent
    severity = "moderate" if magnitude < 15 else "high"
    return {
        "task": "change_vqa",
        "query": query,
        "image_t1_id": image_t1_id,
        "image_t2_id": image_t2_id,
        "answer_text": "Built-up area has expanded along the eastern edge, replacing what was previously bare soil.",
        "change_categories": cats,
        "change_magnitude_pct": magnitude,
        "severity": severity,
        "change_mask_rle": None,
        "confidence": conf,
        "answer_numeric": magnitude,
        "answer_unit": "percent",
        "answer_temporal_ref": "2021-2023",
        "per_tile_confidence": {f"{image_t1_id}_tile_0": round(conf-0.02,3), f"{image_t2_id}_tile_0": conf},
    }

def dummy_optical_sar_fusion(fused_repr, query: str, optical_image_id: str = "s2_001", sar_image_id: str = "s1_001") -> Dict[str, Any]:
    rnd = random.Random(_seed(query + "fusion"))
    opt = round(0.80 + rnd.random()*0.06, 2)
    sar = round(0.72 + rnd.random()*0.08, 2)
    fused = round(min(0.95, (opt+sar)/2 + 0.08 + rnd.random()*0.04), 2)
    return {
        "task": "optical_sar_fusion",
        "query": query,
        "optical_image_id": optical_image_id,
        "sar_image_id": sar_image_id,
        "answer_text": "The fused analysis shows built-up regions concentrated in the southwest, with a water body along the northern boundary confirmed by both optical reflectance and SAR backscatter.",
        "class_map_rle": {
            "built-up": "RLE_STRING_HERE",
            "water": "RLE_STRING_HERE",
            "other": "RLE_STRING_HERE",
        },
        "unlabeled_rle": "RLE_UNLABELED",
        "per_modality_confidence": {
            "optical": opt,
            "sar": sar,
            "fused": fused,
        },
        "answer_numeric": fused,
        "answer_unit": "confidence",
        "per_tile_confidence": {f"{optical_image_id}_tile_0": opt, f"{sar_image_id}_tile_0": sar},
        "attention_maps": None,
    }

# helper to build chart specs matching frontend expectations
def vqa_chart(conf: float) -> Dict[str, Any]:
    return {"type": "donut", "title": "Land-cover confidence", "data": [
        {"name": "Agriculture", "value": conf},
        {"name": "Settlement", "value": round(max(0.3, conf-0.22),2)},
        {"name": "Forest", "value": round(max(0.3, conf-0.13),2)},
    ], "unit": "%", "note": "RS-VQA • dummy"}

def fusion_chart(per_mod: Dict[str,float]) -> Dict[str, Any]:
    return {"type": "bar", "title": "Modality confidence", "data": [
        {"name": "Optical", "value": per_mod["optical"]},
        {"name": "SAR", "value": per_mod["sar"]},
        {"name": "Fused", "value": per_mod["fused"]},
    ], "unit": "confidence", "note": "CROMA cross-attention • dummy"}
