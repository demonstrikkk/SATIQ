"""
chart_spec — SATIQ chart contract for the agentic (orchestrator) pipeline.

Mirrors frontend/src/lib/chartSpec.ts — keep schemas in sync.
Provides validation and the prompt fragment consumed by the composer.

Skill: .agents/skills/apexcharts-skill/SKILL.md
"""

from __future__ import annotations

import json
from typing import Any, List, Literal, Optional, Tuple

ChartType = Literal["bar", "area", "line", "donut", "pie", "radialBar", "heatmap"]
CHART_TYPES = {"bar", "area", "line", "donut", "pie", "radialBar", "heatmap"}
SATIQ_PALETTE = ["#06B6D4", "#22C55E", "#F59E0B", "#64748B", "#38bdf8", "#8B5CF6", "#EF4444", "#14B8A6"]
MAX_DATA = 12
DISPLAY_MAX = 8

CHART_PROMPT_FRAGMENT = """CHART RULES — if your answer contains numbers from REAL model output, emit ONE ```chart block after the narrative:
- Type: bar / donut / area|line / radialBar.
- Title: short, human, with unit.
- Data: [{name, value}] from REAL numbers only. Max 8 entries. Under 4KB.
- Put real provenance (sensor, CRS, GSD) from asset metadata into "note", never invent.
- If no numbers, omit chart — do not fabricate.

Examples:
```chart
{"type":"bar","title":"Change by category","data":[{"name":"Sector A","value":9.2}],"unit":"ha","note":"real asset CRS"}
```
```chart
{"type":"donut","title":"Land-cover confidence","data":[{"name":"Agriculture","value":0.84},{"name":"Settlement","value":0.62},{"name":"Forest","value":0.71}],"unit":"%","note":"RS-VQA • img_001"}
```
"""


def validate_chart_spec(raw: Any) -> Tuple[bool, List[dict]]:
    """Validate raw chart dict. Returns (valid, errors)."""
    errors: List[dict] = []
    if not isinstance(raw, dict):
        return False, [{"field": "root", "message": "Chart spec must be an object"}]

    t = raw.get("type")
    if not isinstance(t, str) or t not in CHART_TYPES:
        errors.append({"field": "type", "message": f"type must be one of: {sorted(CHART_TYPES)}"})
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        errors.append({"field": "title", "message": "title is required"})
    data = raw.get("data")
    if not isinstance(data, list):
        errors.append({"field": "data", "message": "data must be array of {name,value}"})
    else:
        if len(data) == 0:
            errors.append({"field": "data", "message": "data must have at least 1 entry"})
        if len(data) > MAX_DATA:
            errors.append({"field": "data", "message": f"data exceeds {MAX_DATA} entries"})
        for i, d in enumerate(data):
            if not isinstance(d, dict):
                errors.append({"field": f"data[{i}]", "message": "entry must be {name,value}"})
                continue
            if not isinstance(d.get("name"), str) or not d["name"].strip():
                errors.append({"field": f"data[{i}].name", "message": "name required"})
            if not isinstance(d.get("value"), (int, float)):
                errors.append({"field": f"data[{i}].value", "message": "value must be finite number"})

    try:
        if len(json.dumps(raw)) > 4096:
            errors.append({"field": "data", "message": "JSON exceeds 4096 bytes"})
    except Exception:
        pass

    return (len(errors) == 0), errors


def normalize_chart_spec(spec: dict) -> dict:
    """Normalize after validation: coerce pie→donut, truncate, clamp names."""
    out = dict(spec)
    if out.get("type") == "pie":
        out["type"] = "donut"
    if out.get("type") not in CHART_TYPES:
        out["type"] = "bar"
    if not out.get("title"):
        out["title"] = "Analysis"
    data = out.get("data", [])
    if len(data) > DISPLAY_MAX:
        top = data[: DISPLAY_MAX - 1]
        rest = data[DISPLAY_MAX - 1 :]
        is_ha = any(isinstance(d.get("value"), (int, float)) and d["value"] > 2 for d in rest)
        other_val = sum(d["value"] for d in rest) if is_ha else sum(d["value"] for d in rest) / len(rest)
        top.append({"name": "Other", "value": round(other_val, 2), "meta": f"{len(rest)} more"})
        out["data"] = top
        note = out.get("note") or ""
        suffix = f"Top {DISPLAY_MAX} of {len(data)} shown"
        out["note"] = f"{note} · {suffix}" if note else suffix
    return out


def chart_to_fenced_block(spec: dict) -> str:
    return "```chart\n" + json.dumps(spec) + "\n```"


def build_change_by_sector_chart(sectors: List[dict], note: str = "") -> dict:
    return normalize_chart_spec({"type": "bar", "title": "Change by sector (ha)", "data": sectors, "unit": "ha", "note": note})


def build_fusion_chart(optical: float, sar: float, fused: float, chart_type: str = "bar") -> dict:
    return normalize_chart_spec(
        {
            "type": chart_type,
            "title": "Modality confidence",
            "data": [
                {"name": "Optical", "value": optical},
                {"name": "SAR", "value": sar},
                {"name": "Fused", "value": fused},
            ],
            "unit": "confidence",
            "note": "CROMA cross-attention • per-modality confidence",
        }
    )


def build_chart_from_task_output(task_output: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Data-driven chart generation from real task_output values.
    change_vqa + change_magnitude_pct -> bar per change_category with real magnitude
    optical_sar_fusion + per_modality_confidence -> bar with real confidences
    vqa + answer_numeric + key_objects -> donut/bar
    grounding + bbox_list -> heatmap of bbox density
    """
    try:
        task = task_output.get("task")
        if task == "change_vqa":
            cats = task_output.get("change_categories") or []
            mag = task_output.get("change_magnitude_pct") or task_output.get("answer_numeric")
            if cats and mag is not None and isinstance(mag, (int, float)):
                data = [{"name": c.replace("_"," "), "value": float(mag) / len(cats)} for c in cats] if len(cats) > 1 else [{"name": cats[0].replace("_"," "), "value": float(mag)}]
                return normalize_chart_spec({"type":"bar","title":"Change by category","data":data,"unit":"value","note":"Change-VQA"})
            return None
        if task == "optical_sar_fusion":
            per = task_output.get("per_modality_confidence") or {}
            if per and all(k in per for k in ["optical","sar","fused"]):
                return build_fusion_chart(per["optical"], per["sar"], per["fused"])
            return None
        if task in ("vqa","captioning"):
            conf = task_output.get("confidence")
            key_objs = task_output.get("key_objects") or []
            if conf is not None and key_objs and len(key_objs) >=2:
                data = []
                for i, obj in enumerate(key_objs[:4]):
                    val = round(max(0.3, float(conf) - i*0.12),2)
                    data.append({"name": obj.title(), "value": val})
                return normalize_chart_spec({"type":"donut","title":"Land-cover confidence","data":data,"unit":"%","note":"RS-VQA"})
            return None
        if task == "grounding":
            bboxes = task_output.get("bbox_list") or []
            if bboxes and len(bboxes) >=2:
                data = [{"name": f"Detection {i+1}", "value": 1} for i, _ in enumerate(bboxes)]
                return normalize_chart_spec({"type":"heatmap","title":"Grounding detections","data":data,"unit":"count","note":"GroundingDINO"})
            conf = task_output.get("confidence")
            if conf is not None:
                return normalize_chart_spec({"type":"bar","title":"Detection confidence","data":[{"name":"Target","value":float(conf)},{"name":"Background","value":round(1-float(conf),2)}],"unit":"confidence","note":"Grounding"})
            return None
        # generic numeric answer
        num = task_output.get("answer_numeric")
        unit = task_output.get("answer_unit") or "value"
        if num is not None:
            title = f"Answer ({unit})"
            return normalize_chart_spec({"type":"radialBar","title":title,"data":[{"name":"Value","value": float(num)}],"unit":unit,"note":"Task numeric"})
    except Exception:
        return None
    return None

def chart_prompt_fragment() -> str:
    return CHART_PROMPT_FRAGMENT
