"""GeoJSON export — bbox/mask RLE → FeatureCollection."""
from __future__ import annotations
from typing import Dict, Any, List, Optional
import json

def _bbox_to_polygon(bbox: List[float], from_normalized: bool = False) -> List[List[float]]:
    """bbox [x,y,w,h] or [x_min,y_min,x_max,y_max] normalized or xyxy pixels.
    For GeoJSON we treat as WGS84 approx: map normalized [0,1] to [0,1] degree box for demo.
    Real would use image CRS transform.
    """
    if len(bbox) == 4:
        # detect format: if bbox is xyxy with values >1, assume pixels normalized by 512
        if max(bbox) > 1.5:
            # xyxy pixels 0-512 -> normalize
            x1,y1,x2,y2 = [b/512 for b in bbox]  # type: ignore
        elif bbox[2] <= 1.5 and bbox[3] <= 1.5 and bbox[0] < 1 and bbox[1] < 1:
            # check if is x,y,w,h vs xyxy: if w/h small, it's w,h
            # need heuristic: if bbox[2] - bbox[0] <0.5 and bbox[3]-bbox[1] <0.5, treat as xywh vs xyxy?
            # For grounding bbox_normalized [0.18,0.09,0.47,0.42] is xyxy
            x1,y1,x2,y2 = bbox  # type: ignore
        else:
            x1,y1,x2,y2 = bbox  # type: ignore
        # polygon ring clockwise
        return [[x1,y1],[x2,y1],[x2,y2],[x1,y2],[x1,y1]]
    return [[0,0],[1,0],[1,1],[0,1],[0,0]]

def _rle_to_polygons(rle: str) -> List[List[List[float]]]:
    """Decode RLE string to polygons — dummy: returns bbox polygon placeholder.
    Real would use pycocotools mask decode.
    """
    # mock: treat RLE as single bbox covering center
    return [[[0.3,0.3],[0.7,0.3],[0.7,0.7],[0.3,0.7],[0.3,0.3]]]

def export_geojson(task_output: Dict[str, Any], crs: str = "EPSG:4326") -> Dict[str, Any]:
    """Export task_output to GeoJSON FeatureCollection.
    - grounding bbox → Polygon
    - change_mask_rle → MultiPolygon
    - class_map_rle → labeled Features
    """
    features: List[Dict[str, Any]] = []
    task = task_output.get("task")
    # grounding
    if task == "grounding":
        bboxes = task_output.get("bbox_list") or []
        if not bboxes and task_output.get("bbox_xyxy"):
            bboxes = [task_output["bbox_xyxy"]]
        elif not bboxes and task_output.get("bbox"):
            bboxes = [task_output["bbox"]]
        for i, bb in enumerate(bboxes):
            # bb may be xyxy pixels or normalized
            poly = _bbox_to_polygon(bb)
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [poly]},
                "properties": {"label": f"grounding_{i}", "confidence": task_output.get("confidence"), "bbox": bb}
            })
        if task_output.get("mask_rle"):
            for poly in _rle_to_polygons(task_output["mask_rle"]):
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [poly]},
                    "properties": {"label": "mask", "source": "grounding"}
                })
    # change_vqa
    elif task == "change_vqa":
        cats = task_output.get("change_categories") or []
        for cat in cats:
            features.append({
                "type": "Feature",
                "geometry": {"type": "Polygon", "coordinates": [_bbox_to_polygon([0.2,0.2,0.6,0.5])]},
                "properties": {"change_category": cat, "magnitude_pct": task_output.get("change_magnitude_pct")}
            })
        if task_output.get("change_mask_rle"):
            for poly in _rle_to_polygons(task_output["change_mask_rle"]):
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [poly]},
                    "properties": {"label": "change_mask"}
                })
    # fusion
    elif task == "optical_sar_fusion":
        cm = task_output.get("class_map_rle") or {}
        for cls, rle in cm.items():
            for poly in _rle_to_polygons(rle):
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Polygon", "coordinates": [poly]},
                    "properties": {"class": cls, "per_modality_confidence": task_output.get("per_modality_confidence")}
                })
    # generic: if task_output has bbox
    if not features and task_output.get("bbox"):
        features.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_bbox_to_polygon(task_output["bbox"])]},
            "properties": {"label": task, "confidence": task_output.get("confidence")}
        })
    if not features:
        # empty collection for text-only vqa
        return {"type": "FeatureCollection", "features": [], "crs": {"type":"name","properties":{"name":crs}}}
    fc = {
        "type": "FeatureCollection",
        "features": features,
        "crs": {"type": "name", "properties": {"name": crs}},
        "properties": {"task": task, "confidence": task_output.get("confidence")}
    }
    return fc

def export_geojson_bytes(task_output: Dict[str, Any], crs: str = "EPSG:4326") -> bytes:
    return json.dumps(export_geojson(task_output, crs), indent=2).encode()
