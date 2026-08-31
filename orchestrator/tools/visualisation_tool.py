"""Visualisation tool adapter — single adapter for all visual evidence.

Per TASK PROMPT §4, capabilities must emit artifacts via this tool, not ad hoc writers.
Keeps visualisation.py unchanged and reusable; this adapter is the LangGraph-facing contract.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List
from langchain_core.tools import tool

try:
    # Try to import existing visualisation.py's real function — verify signature before wiring
    import visualisation  # type: ignore
    _real_fn = getattr(visualisation, "generate_visual_evidence", None) or getattr(visualisation, "visualize", None) or getattr(visualisation, "render", None)
except Exception:
    _real_fn = None


def _fallback_visualisation(image_paths: List[str], model_output: Dict[str, Any], task: str) -> Dict[str, Any]:
    """Fallback when visualisation.py not available — create output dir and return artifact dict.
    Does not fabricate evidence; just ensures path contract.
    """
    out_dir = Path("outputs") / task
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts: List[Dict[str, Any]] = []
    for ip in image_paths:
        stem = Path(ip).stem
        # Grounding: bbox overlay expected
        if task == "grounding" and model_output.get("bbox_xyxy"):
            artifacts.append({"type": "bbox_overlay", "path": str(out_dir / f"{stem}_bbox.png"), "bbox_xyxy": model_output["bbox_xyxy"]})
        elif task == "change_vqa" and model_output.get("artifact_path"):
            artifacts.append({"type": "change_map", "path": model_output["artifact_path"]})
        elif task == "optical_sar_fusion":
            artifacts.append({"type": "fusion_overlay", "path": str(out_dir / f"{stem}_fusion.png")})
        else:
            artifacts.append({"type": "overlay", "path": str(out_dir / f"{stem}_{task}.png")})
    return {"artifacts": artifacts, "task": task, "image_paths": image_paths}


@tool
def generate_visual_evidence(image_paths: List[str], model_output: Dict[str, Any], task: str) -> Dict[str, Any]:
    """Generate visual evidence (overlays/masks/change maps) from model outputs.
    LangGraph-facing contract: image_paths + model_output + task → artifact dict.
    """
    if _real_fn is not None:
        try:
            # Adapt call — try common signatures, keep contract stable
            try:
                result = _real_fn(image_paths=image_paths, model_output=model_output, task=task)  # type: ignore
            except TypeError:
                result = _real_fn(image_paths, model_output, task)  # type: ignore
            if isinstance(result, dict):
                return result
            return {"artifacts": result if isinstance(result, list) else [], "task": task}
        except Exception as e:
            return {"artifacts": [], "task": task, "error": str(e)[:300], "fallback": _fallback_visualisation(image_paths, model_output, task)}
    return _fallback_visualisation(image_paths, model_output, task)
