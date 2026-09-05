"""Tool schemas for native function calling (Groq/OpenAI compatible).

Exposes 4 model shims + 6 deterministic helpers as OpenAI tool specs.
Router/planner can use tool_choice="auto" to let the LLM select the correct
task instead of regex-parsing free text. Keeps single-GPU demo simple:
all tools are called via asyncio.to_thread inside task_agent — no extra
process.
"""
from __future__ import annotations
from typing import List, Dict, Any

# 4 model shims — the LLM should select exactly one per turn
MODEL_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "run_vqa",
            "description": "Model1 GeoChat-7B VQA — answer free-form question on single satellite image (land cover, vegetation, water, urban). Use for What/Describe/Is there/How many without bbox.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Resolved asset path or asset_id (e.g. img_001)"},
                    "query": {"type": "string", "description": "User question"},
                },
                "required": ["image_path", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_grounding",
            "description": "Model2 GroundingDINO Swin-T — localise text query to bbox via percentile 2-98 + Swin cross-attention. Use for where/locate/bounding box/ground.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string", "description": "Single optical image path"},
                    "query": {"type": "string", "description": "Referring expression, e.g. 'the water body in the north'"},
                },
                "required": ["image_path", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_change_vqa",
            "description": "Model3 Prithvi+Vicuna Change-VQA hybrid — bi-temporal change QA via NDVI/NDBI/NDWI + fusion confidence. Use for change/between/what changed/T1 T2.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_t1": {"type": "string", "description": "Earlier optical image path"},
                    "image_t2": {"type": "string", "description": "Later optical image path"},
                    "query": {"type": "string", "description": "Change question"},
                },
                "required": ["image_t1", "image_t2", "query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_fusion",
            "description": "Model4 CROMA dual ViT 12-band optical + 2-band SAR cross-attention fusion — 19 classes + modality contributions + spatial CAM. Use for optical+SAR / Sentinel-1+2 / fusion queries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "optical_path": {"type": "string", "description": "Sentinel-2 optical patch path"},
                    "sar_path": {"type": "string", "description": "Sentinel-1 SAR path"},
                    "query": {"type": "string", "description": "Fusion question"},
                },
                "required": ["optical_path", "sar_path", "query"],
            },
        },
    },
]

# 6 deterministic helpers — no GPU, can run before/after model
DETERMINISTIC_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "compute_spectral_indices",
            "description": "Compute NDVI=(NIR-Red)/(NIR+Red), NDWI, NDBI, EVI from Sentinel-2 bands B02/B03/B04/B08/B11. Fails closed with null if required bands missing — never uses dummy_indices_trace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "asset_id": {"type": "string", "description": "Asset to compute on"},
                    "indices": {"type": "array", "items": {"type": "string", "enum": ["ndvi", "ndwi", "ndbi", "evi"]}, "description": "Indices requested"},
                },
                "required": ["asset_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_area",
            "description": "Calculate area in ha/km2 from bbox [x1,y1,x2,y2] (pixel or normalized [0,1]) given GSD and CRS. Clamps bbox to [0,1] or image bounds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bbox": {"type": "array", "items": {"type": "number"}, "description": "bbox_xyxy or bbox_normalized"},
                    "gsd": {"type": "number", "description": "Ground sample distance in meters"},
                    "crs": {"type": "string", "description": "CRS e.g. EPSG:4326"},
                    "width": {"type": "number", "description": "Optional image width for normalized→pixel"},
                    "height": {"type": "number", "description": "Optional image height"},
                },
                "required": ["bbox", "gsd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "geocode_region",
            "description": "Resolve region name to WGS84 bbox [minx,miny,maxx,maxy] via builtin gazetteer + optional GeoJSON. No external API.",
            "parameters": {
                "type": "object",
                "properties": {
                    "region_name": {"type": "string", "description": "Region, e.g. Karnataka, Sector A"},
                },
                "required": ["region_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "crop_bbox",
            "description": "CPU FFmpeg crop: crop geotiff to bbox w/h/x/y via ffmpeg -vf crop, then scale to out_size. Runs on CPU, no VRAM. Returns PNG path for next-turn VQA / coreference.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_path": {"type": "string"},
                    "bbox_xyxy": {"type": "array", "items": {"type": "number"}, "description": "[x1,y1,x2,y2] pixel"},
                    "out_size": {"type": "array", "items": {"type": "number"}, "description": "[w,h] default 512x512"},
                },
                "required": ["image_path", "bbox_xyxy"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_visual_evidence",
            "description": "Generate visual artifact (bbox overlay, change map, CROMA 4-panel, CAM) via visualisation_tool. Delegates to real visualisation.py if present, else returns artifact metadata.",
            "parameters": {
                "type": "object",
                "properties": {
                    "image_paths": {"type": "array", "items": {"type": "string"}},
                    "task": {"type": "string", "enum": ["vqa", "grounding", "change_vqa", "optical_sar_fusion"]},
                },
                "required": ["image_paths", "task"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "retrieve_history",
            "description": "Hybrid RAG retrieve: Chroma semantic + SQLite recency for conversation history. Returns top_k snippets with query→answer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "integer", "description": "default 3"},
                },
                "required": ["query"],
            },
        },
    },
]

REGISTERED_TOOLS: List[Dict[str, Any]] = MODEL_TOOLS + DETERMINISTIC_TOOLS

# Lightweight router-only subset (reduces tokens for groq/compound-mini 10-token budget)
ROUTER_TOOLS: List[Dict[str, Any]] = MODEL_TOOLS  # router only needs to pick task

TOOL_NAME_TO_TASK = {
    "run_vqa": "vqa",
    "run_grounding": "grounding",
    "run_change_vqa": "change_vqa",
    "run_fusion": "optical_sar_fusion",
    # alias used in some prompts
    "run_optical_sar_fusion": "optical_sar_fusion",
}
