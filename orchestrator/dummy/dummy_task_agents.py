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
    ql = query.lower()
    # query-aware: agriculture vs water vs building etc.
    if any(k in ql for k in ["agriculture","agricultural","crop","cultivat","field","farm","cattle","pasture","grazing"]):
        label = "agricultural field"
        sector = "central sector"
        bbox_norm = [0.22, 0.31, 0.68, 0.72]
        bbox_xyxy = [140, 160, 380, 340]
        answer_text = f"Agricultural land detected in the {sector} with confidence {{conf:.2f}}. BBox (normalized) {{bbox_norm}} corresponds to xyxy {{bbox_xyxy}}."
    elif any(k in ql for k in ["building","built-up","settlement","urban","house","construction","development"]):
        label = "built-up area"
        sector = "eastern sector"
        bbox_norm = [0.52, 0.28, 0.81, 0.61]
        bbox_xyxy = [280, 150, 420, 300]
        answer_text = f"Built-up area detected in the {sector} with confidence {{conf:.2f}}. BBox (normalized) {{bbox_norm}} corresponds to xyxy {{bbox_xyxy}}."
    elif any(k in ql for k in ["cave","caves"]):
        label = "cave"
        sector = "rocky northern ridge"
        bbox_norm = [0.33, 0.12, 0.41, 0.24]
        bbox_xyxy = [180, 60, 240, 130]
        answer_text = f"No caves are visible in this high-resolution optical image (10 m GSD, EPSG:32617). The terrain shows agricultural fields and settlement, but no karst or cave signatures were detected. Confidence {{conf:.2f}}."
    elif any(k in ql for k in ["forest","tree","vegetation","wood"]):
        label = "forest patch"
        sector = "western edge"
        bbox_norm = [0.08, 0.32, 0.21, 0.68]
        bbox_xyxy = [50, 170, 130, 330]
        answer_text = f"Forest patch detected along the {sector} with confidence {{conf:.2f}}. BBox (normalized) {{bbox_norm}} corresponds to xyxy {{bbox_xyxy}}."
    elif any(k in ql for k in ["water","lake","river","pond","reservoir"]):
        label = "water body"
        sector = "northern sector"
        bbox_norm = [0.18, 0.09, 0.47, 0.42]
        bbox_xyxy = [120, 45, 310, 210]
        answer_text = f"Water body detected in the {sector} with confidence {{conf:.2f}}. BBox (normalized) {{bbox_norm}} corresponds to xyxy {{bbox_xyxy}}."
    else:
        label = "target"
        sector = "central sector"
        bbox_norm = [0.25, 0.25, 0.62, 0.58]
        bbox_xyxy = [150, 130, 340, 290]
        answer_text = f"{label.capitalize()} detected in the {sector} with confidence {{conf:.2f}}. BBox (normalized) {{bbox_norm}} corresponds to xyxy {{bbox_xyxy}}."
    jitter = (rnd.random()-0.5)*0.04
    bbox_norm = [round(max(0,min(1, v+jitter)), 3) for v in bbox_norm]
    conf = round(0.82 + rnd.random()*0.08, 2)
    # fill template
    answer_text = answer_text.format(conf=conf, bbox_norm=bbox_norm, bbox_xyxy=bbox_xyxy)
    bbox_list = [bbox_xyxy]
    if "multiple" in ql or "all" in ql:
        bbox_list = [bbox_xyxy, [310, 210, 420, 320]]
    phrase_map = {label: [bbox_xyxy]}
    return {
        "task": "grounding",
        "query": query,
        "image_id": image_id,
        "answer_text": answer_text,
        "bbox_normalized": bbox_norm,
        "bbox_xyxy": bbox_xyxy,
        "bbox": bbox_norm,
        "bbox_list": bbox_list,
        "phrase_grounding_map": phrase_map,
        "mask_rle": None,
        "confidence": conf,
        "detections": len(bbox_list),
        "status": "OK",
        "answer_numeric": float(len(bbox_list)),
        "answer_unit": "count",
        "per_tile_confidence": {f"{image_id}_tile_0": conf},
        "attention_maps": None,
        "detected_label": label,
        "sector": sector,
    }

def dummy_change_vqa(fused_repr, query: str, image_t1_id: str = "img_2021", image_t2_id: str = "img_2023") -> Dict[str, Any]:
    import re
    rnd = random.Random(_seed(query + "change"))
    ql = query.lower()
    cats = ["built-up_increase"]
    if "water" in ql:
        cats = ["water_increase", "built-up_increase"]
    elif "vegetation" in ql or "forest" in ql:
        cats = ["vegetation_decrease"]
    elif "parliament" in ql:
        cats = ["built-up_increase"]
    conf = round(0.75 + rnd.random()*0.12, 2)
    magnitude = round(12.5 + rnd.random()*8, 2)
    severity = "moderate" if magnitude < 15 else "high"
    # extract years from query for temporal ref (e.g., 2024 to 2026)
    years = re.findall(r"20\d{2}", query)
    if len(years) >= 2:
        temporal_ref = f"{years[0]}-{years[1]}"
        year_phrase = f"between {years[0]} and {years[1]}"
    elif len(years) == 1:
        temporal_ref = years[0]
        year_phrase = f"around {years[0]}"
    else:
        temporal_ref = "2021-2023"
        year_phrase = "between 2021 and 2023"
    # query-aware answer
    if "parliament" in ql:
        answer_text = f"Parliament building construction shows clear expansion {year_phrase}. New structural footprint expanded along the central and eastern zones, with +{magnitude:.1f}% built-up increase. Scaffolding and roof structures visible in the later image indicate ongoing construction."
    elif "water" in ql and "parliament" not in ql:
        answer_text = f"Water extent changed {year_phrase} with +{magnitude:.1f}% increase along the eastern edge."
    else:
        answer_text = f"Built-up area has expanded {year_phrase} along the eastern edge, replacing what was previously bare soil (+{magnitude:.1f}% change)."
    return {
        "task": "change_vqa",
        "query": query,
        "image_t1_id": image_t1_id,
        "image_t2_id": image_t2_id,
        "answer_text": answer_text,
        "change_categories": cats,
        "change_magnitude_pct": magnitude,
        "severity": severity,
        "change_mask_rle": None,
        "confidence": conf,
        "answer_numeric": magnitude,
        "answer_unit": "percent",
        "answer_temporal_ref": temporal_ref,
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
