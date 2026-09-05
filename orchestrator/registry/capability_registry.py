"""Capability registry — single source of truth for tool legality + dynamic selection.

No hardcoded C: weights. All paths via settings. Used by guardrails and planner prompt.
"""
from __future__ import annotations
from typing import Dict, Any, List

CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "vqa": {
        "task_type": "vqa",
        "tool": "run_vqa",
        "description": "Model1 GeoChat-7B merged (13.5GB, 4bit 7GB) — answers free-form questions on single satellite image (land cover, vegetation, water, urban) via ask_geochat(image_path, question) -> text. Input: single image (PNG/JPG/GeoTIFF) + query. Output: answer_text + confidence None. Use when query asks What/Describe/Is there/How many without bbox.",
        "required_assets": 1,
        "required_modality": ["optical", "multispectral", "sar"],
        "encoder": "clip",
        "inference": "models/model1/run_inference.py",
        "guardrail_schema": {"needs_bbox": False},
        "vram_mb": 7000,
        "timeout_ms": 12000,
        "retryable": False,
        "gpu": True,
    },
    "captioning": {
        "task_type": "captioning",
        "tool": "run_vqa",
        "description": "Same Model1 GeoChat-7B — caption single image (subset of VQA)",
        "required_assets": 1,
        "required_modality": ["optical", "multispectral"],
        "encoder": "clip",
        "inference": "models/model1/run_inference.py",
        "guardrail_schema": {"needs_bbox": False},
        "vram_mb": 7000,
        "timeout_ms": 12000,
        "retryable": False,
        "gpu": True,
    },
    "grounding": {
        "task_type": "grounding",
        "tool": "run_grounding",
        "description": "Model2 GroundingDINO Swin-T (~170M) fine-tuned on BigEarthNet S2 — localises text query to bbox via load_and_convert_s2(patch_dir,224) percentile 2-98 + run_inference(tensor,query) -> boxes normalized xyxy [0,1] + scores. Input: single optical image. Output: bbox_xyxy pixel + bbox_normalized [0-1] + confidence. Use when query contains where/locate/bounding box/ground.",
        "required_assets": 1,
        "required_modality": ["optical", "multispectral"],
        "encoder": "swin",
        "inference": "models/model2/visualize_pipeline_graph.py",
        "guardrail_schema": {"needs_bbox": True},
        "vram_mb": 6000,
        "timeout_ms": 8000,
        "retryable": False,
        "gpu": True,
    },
    "change_vqa": {
        "task_type": "change_vqa",
        "tool": "run_change_vqa",
        "description": "Model3 Prithvi-100M + Vicuna-7B (hybrid index + fusion confidence) — bi-temporal change QA via compute_indices NDVI/NDBI/NDWI + fusion_change_confidence. Input: two optical images T1 T2. Output: answer_text + change_categories + deltas + confidence. Use when query mentions change/between/what changed/T1 T2.",
        "required_assets": 2,
        "required_modality": ["optical", "multispectral"],
        "encoder": "prithvi",
        "inference": "models/model3/visualize_index_hybrid.py",
        "guardrail_schema": {"needs_bbox": False},
        "vram_mb": 8000,
        "timeout_ms": 10000,
        "retryable": False,
        "gpu": True,
    },
    "optical_sar_fusion": {
        "task_type": "optical_sar_fusion",
        "tool": "run_fusion",
        "description": "Model4 CROMA dual ViT (12-band optical 120×120 + 2-band SAR) — cross-attention fusion via Model4Engine.predict(opt,sar,threshold) -> 19 classes + per_modality + spatial_cam. Input: optical + SAR co-registered. Output: natural_summary + per_modality_confidence + detected_classes. Use when query has optical+SAR / Sentinel-1+2 / fusion.",
        "required_assets": 2,
        "required_modality": ["optical+sar"],
        "encoder": "croma",
        "inference": "models/model4/infer.py",
        "guardrail_schema": {"needs_bbox": False},
        "vram_mb": 6500,
        "timeout_ms": 10000,
        "retryable": False,
        "gpu": True,
    },
}

# Tool → capability reverse index (single source; TOOL_NAME_TO_TASK in tool_schemas must match)
TOOL_TO_CAPABILITY = {v["tool"]: k for k,v in CAPABILITIES.items() if "tool" in v}

# Deterministic helpers (no model)
DETERMINISTIC: Dict[str, Dict[str, Any]] = {
    "area_calculator": {"needs_bbox": True},
    "ndvi": {"needs_bands": ["B04", "B08"]},
    "spectral_indices": {"needs_bands": ["B02", "B03", "B04", "B08"]},
}


def get_capability(task_type: str) -> Dict[str, Any] | None:
    return CAPABILITIES.get(task_type)


def validate_legality(task_type: str, assets: List[Dict[str, Any]]) -> tuple[bool, str]:
    """Check if task_type is legal for given assets. Returns (ok, reason)."""
    cap = get_capability(task_type)
    if not cap:
        # non-geospatial intents are not in registry but are legal (they skip models)
        if task_type in ("greeting", "chitchat", "help", "out_of_scope", "general"):
            return True, "non-geospatial skip"
        return False, f"unknown task_type {task_type}"
    need = cap["required_assets"]
    have = len(assets)
    if have < need:
        return False, f"{task_type} needs {need} assets but have {have}"
    # modality checks
    if task_type == "optical_sar_fusion":
        mods = [(a.get("modality") or "").lower() for a in assets]
        has_opt = any(m in ("optical", "multispectral") for m in mods)
        has_sar = any(m == "sar" for m in mods)
        if not (has_opt and has_sar):
            return False, "fusion needs one optical and one sar"
    return True, "ok"


def registry_prompt_fragment() -> str:
    lines = ["CAPABILITIES (choose exactly one):"]
    for k, v in CAPABILITIES.items():
        lines.append(f"- {k}: {v['description']} (needs {v['required_assets']} image(s))")
    lines.append("- greeting/chitchat/help/out_of_scope: no image needed, answer directly")
    return "\n".join(lines)
