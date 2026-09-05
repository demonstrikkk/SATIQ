"""Shim for model2 (GroundingDINO) — wraps visualize_pipeline_graph.py without editing.

Original pipeline: load_and_convert_s2(patch_dir,224) → Normalize → build_groundingdino + run_inference → boxes [0,1] xyxy + scores
We adapt single image_path (resolved via image_pipeline) to patch_dir handling: if path is single tif/png, we still support via PIL fallback.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import sys
import torch
import numpy as np
import cv2
from PIL import Image
import torchvision.transforms as T

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL2_ROOT = REPO_ROOT / "models" / "model2"

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]

_MODEL = None
_DEVICE = None

def _ensure_model():
    global _MODEL, _DEVICE
    if _MODEL is not None:
        return _MODEL, _DEVICE
    sys.path.insert(0, str(MODEL2_ROOT))
    import config as cfg  # type: ignore
    from train import build_groundingdino  # type: ignore
    _DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    cfg_path = Path(cfg.PRETRAINED_DIR) / cfg.GDINO_CONFIG_FILES[cfg.MODEL_TYPE] if hasattr(cfg, "GDINO_CONFIG_FILES") else Path(cfg.GDINO_CONFIG)  # type: ignore
    # Fallback to merged_model path logic
    try:
        w_path = Path(cfg.PRETRAINED_DIR) / cfg.GDINO_WEIGHT_FILES[cfg.MODEL_TYPE]
    except Exception:
        w_path = Path(cfg.GDINO_WEIGHTS)  # type: ignore
    _MODEL = build_groundingdino(str(cfg_path), str(w_path), _DEVICE)
    _MODEL.eval()
    return _MODEL, _DEVICE

def _load_single_image_as_tensor(image_path: str, size: int):
    # If it's a BigEarthNet patch dir (contains *_B0*.tif), use original load_and_convert_s2
    p = Path(image_path)
    if p.is_dir() and any(p.glob("*_B0*.tif*")):
        sys.path.insert(0, str(MODEL2_ROOT))
        from visualize_pipeline_graph import load_and_convert_s2  # type: ignore
        tensor, raw = load_and_convert_s2(p, size=size)
        return tensor, raw, size, size
    # Single file: PIL → cv2 resize → Normalize (same as grounding post)
    img = Image.open(p).convert("RGB")
    arr = np.array(img).astype(np.float32) / 255.0
    # already 0-1, resize to size
    resized = cv2.resize(arr, (size, size), interpolation=cv2.INTER_LINEAR)
    tensor = torch.from_numpy(resized).permute(2,0,1)
    norm = T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD)
    tensor = norm(tensor)
    # raw for display
    raw = (resized * 255).astype(np.uint8)
    return tensor, raw, size, size

def inference(image_path: str, query: str) -> Dict[str, Any]:
    if not image_path or not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found for Grounding: {image_path}")
    sys.path.insert(0, str(MODEL2_ROOT))
    import config as cfg  # type: ignore
    from train import run_inference  # type: ignore
    size = int(getattr(cfg, "IMAGE_SIZE", 224))
    model, device = _ensure_model()
    tensor, raw, H, W = _load_single_image_as_tensor(image_path, size)
    boxes, scores = run_inference(tensor.unsqueeze(0).to(device), query, model, device, conf_threshold=float(getattr(cfg, "INFERENCE_CONF_THRESHOLD", 0.35)))
    if len(boxes) == 0:
        return {"text": f"No target matching '{query}' detected.", "answer_text": f"No target matching '{query}' detected.", "confidence": None, "bbox_xyxy": None, "bbox_normalized": None, "artifacts": [], "metadata": {"boxes": [], "scores": []}}
    # Take top box
    box = boxes[0]  # tensor [4] normalized xyxy
    score = float(scores[0])
    Wp, Hp = W, H
    # Convert normalized [0,1] to pixel xyxy
    x1 = int(float(box[0]) * Wp)
    y1 = int(float(box[1]) * Hp)
    x2 = int(float(box[2]) * Wp)
    y2 = int(float(box[3]) * Hp)
    bbox_xyxy = [x1, y1, x2, y2]
    bbox_norm = [round(float(box[0]),3), round(float(box[1]),3), round(float(box[2]),3), round(float(box[3]),3)]
    return {
        "text": f"Detected '{query}' with confidence {score:.2f}. BBox {bbox_xyxy} (normalized {bbox_norm})",
        "answer_text": f"Detected '{query}' with confidence {score:.2f}. BBox {bbox_xyxy}",
        "confidence": score,
        "bbox_xyxy": bbox_xyxy,
        "bbox_normalized": bbox_norm,
        "bbox": bbox_norm,
        "artifacts": [{"type": "bbox_overlay", "bbox_xyxy": bbox_xyxy, "bbox_normalized": bbox_norm}],
        "metadata": {"boxes": [bbox_xyxy], "scores": [score], "image_path": image_path, "query": query},
    }
