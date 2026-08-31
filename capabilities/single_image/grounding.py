"""Grounding capability — real GDINO + S2 preprocessing.

Adapted from model2_grounding/visualize_pipeline_graph.py reference (docstring caveats preserved).
Uses ModelManager (§3) so build_groundingdino runs once per process.

Tool contract §5: success {status:success, task:grounding, text, confidence, artifacts, metadata}
              error   {status:error, task:grounding, error_code, message, retryable}
Hard rules: no silent mock fallback — missing checkpoint → MODEL_LOAD_ERROR, never fake bbox.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

try:
    import rasterio
    from PIL import Image
    import torch
except Exception:  # allow import without heavy deps for tests
    rasterio = None
    Image = None
    torch = None

from orchestrator.capabilities.model_manager import manager
from orchestrator.core.config import get_settings

# Link to real model repo at C:\coding\sih\model2_grounding — load config via file location to avoid name collision with model3
import sys as _sys
import importlib.util as _ilu
_MODEL2_REPO = Path(r"C:\coding\sih\model2_grounding")
_MODEL2_GDINO_SRC = _MODEL2_REPO / "gdino_src"
for _p in [str(_MODEL2_REPO), str(_MODEL2_GDINO_SRC)]:
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
try:
    _spec2 = _ilu.spec_from_file_location("model2_grounding_config", _MODEL2_REPO / "config.py")
    _model2_cfg = _ilu.module_from_spec(_spec2)
    assert _spec2.loader is not None
    _spec2.loader.exec_module(_model2_cfg)  # type: ignore
    _MODEL2_AVAILABLE = True
except Exception:
    _model2_cfg = None  # type: ignore
    _MODEL2_AVAILABLE = False

# ---------- Sentinel-2 percentile stretch (verbatim from C:\coding\sih\model2_grounding\visualize_pipeline_graph.py) ----------

def load_and_convert_s2(patch_dir: str | Path, size: int | None = None):
    """Verbatim from visualize_pipeline_graph.py: RGB_BANDS, percentile per band, cv2 resize, ImageNet norm.
    Returns (normalized_tensor CHW) — caller uses normalized_tensor for inference.
    Handles both S2 patch dirs (multiple band files) and single-file PNG/JPG/TIF uploads (any size).
    """
    patch_dir = Path(patch_dir)
    # If patch_dir is actually a single file (PNG/JPG/TIF) — not a dir — load directly via PIL (any size)
    if patch_dir.is_file():
        # Single file upload (website PNG/JPG/TIF, any size) — load via PIL directly, no S2 band logic
        if Image is None:
            raise RuntimeError("Pillow not installed")
        pil = Image.open(patch_dir).convert("RGB")
        # Handle any size - resize to target if needed
        if _MODEL2_AVAILABLE and _model2_cfg is not None:
            size = size or _model2_cfg.IMAGE_SIZE
        else:
            from orchestrator.core.config import get_settings
            size = size or get_settings().image_size
        if pil.size != (size, size):
            pil = pil.resize((size, size), Image.BILINEAR)
        arr = np.array(pil).astype(np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        arr = (arr - mean) / std
        import torch as _torch
        return _torch.from_numpy(arr).permute(2, 0, 1).float()
    # S2 patch dir path
    # Prefer real model2 config
    if _MODEL2_AVAILABLE and _model2_cfg is not None:
        import cv2
        from torchvision import transforms as T
        IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        _normalize = T.Normalize(mean=IMAGENET_MEAN.tolist(), std=IMAGENET_STD.tolist())
        size = size or _model2_cfg.IMAGE_SIZE
        if rasterio is None:
            raise RuntimeError("rasterio is required.")
        # Check if this is actually an S2 patch dir with band files, or a single-file dir (e.g., ingest/t1_rgb with one tif)
        has_bands = any(list(patch_dir.glob(f"*{b}*.tif")) for b in _model2_cfg.RGB_BANDS)
        if not has_bands:
            # Single-file dir (e.g., orchestrator/storage/ingest/t1_rgb contains t1_rgb.tif) — load the single tif via PIL/rasterio
            files = list(patch_dir.glob("*.tif")) + list(patch_dir.glob("*.png")) + list(patch_dir.glob("*.jpg")) + list(patch_dir.glob("*.jpeg"))
            if files:
                # Load the first file in dir as single image
                return load_and_convert_s2(files[0], size=size)
            raise FileNotFoundError(f"S2 band file not found: {patch_dir} (no *B04/B03/B02.tif and no single file)")
        patch_name = patch_dir.name
        channels = []
        raw_channels = []
        for band in _model2_cfg.RGB_BANDS:
            tif_path = patch_dir / f"{patch_name}_{band}.tif"
            if not tif_path.exists():
                # fallback: try any tif with band in name
                cands = list(patch_dir.glob(f"*{band}*.tif"))
                if not cands:
                    raise FileNotFoundError(f"S2 band file not found: {tif_path}")
                tif_path = cands[0]
            with rasterio.open(tif_path) as src:
                native = src.read(1).astype(np.float32)
                raw_channels.append(native)
            p_lo = np.percentile(native, _model2_cfg.S2_PERCENTILE_LOW)
            p_hi = np.percentile(native, _model2_cfg.S2_PERCENTILE_HIGH)
            if p_hi <= p_lo:
                p_lo, p_hi = native.min(), native.max()
            if p_hi <= p_lo:
                channels.append(np.zeros_like(native))
                continue
            data = np.clip(native, p_lo, p_hi)
            data = (data - p_lo) / (p_hi - p_lo)
            if native.shape[0] != size or native.shape[1] != size:
                data = cv2.resize(data, (size, size), interpolation=cv2.INTER_LINEAR)
            channels.append(data)
        import torch as _torch
        img = _torch.from_numpy(np.stack(channels, axis=0))
        normalized_tensor = _normalize(img)
        # raw blackish for visualisation (not used for inference)
        raw_img = np.stack(raw_channels, axis=-1)
        raw_img = np.clip(raw_img / 4000.0, 0, 1)
        # Return tensor CHW normalized + raw for compatibility; caller will handle tensor
        # For API we return normalized tensor shape CHW
        return normalized_tensor
    # Fallback to generic settings if model2 not available
    s = get_settings()
    size = size or s.image_size
    low_p = s.s2_percentile_low
    high_p = s.s2_percentile_high
    patch_dir = Path(patch_dir)
    band_files = sorted(patch_dir.glob("*.tif")) + sorted(patch_dir.glob("*.jp2"))
    if not band_files:
        raise FileNotFoundError(f"No S2 band files in {patch_dir}")
    arrays = []
    for bf in band_files[:4]:
        if rasterio is None:
            raise RuntimeError("rasterio not installed — cannot load S2 patch")
        with rasterio.open(bf) as src:
            arr = src.read(1).astype(np.float32)
            lo, hi = np.percentile(arr, low_p), np.percentile(arr, high_p)
            if hi - lo < 1e-6:
                hi = lo + 1.0
            arr = np.clip((arr - lo) / (hi - lo), 0, 1)
            if Image is not None and size:
                pil = Image.fromarray((arr * 255).astype(np.uint8))
                pil = pil.resize((size, size), Image.BILINEAR)
                arr = np.array(pil).astype(np.float32) / 255.0
            arrays.append(arr)
    if not arrays:
        raise RuntimeError(f"Failed to load S2 bands from {patch_dir}")
    if len(arrays) == 1:
        arrays = arrays * 3
    elif len(arrays) == 2:
        arrays.append(arrays[0])
    hwc = np.stack(arrays[:3], axis=-1)
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    hwc = (hwc - mean) / std
    # Convert HWC to CHW tensor for consistency with real branch
    import torch as _torch
    return _torch.from_numpy(hwc).permute(2, 0, 1).float()


def _resolve_gdino_paths():
    # Prefer real model2 repo paths at C:\coding\sih\model2_grounding
    if _MODEL2_AVAILABLE and _model2_cfg is not None:
        cfg = _model2_cfg.PRETRAINED_DIR / _model2_cfg.GDINO_CONFIG_FILES[_model2_cfg.MODEL_TYPE]
        w = _model2_cfg.PRETRAINED_DIR / _model2_cfg.GDINO_WEIGHT_FILES[_model2_cfg.MODEL_TYPE]
        # Also check checkpoints as fallback (stage1/stage2 fine-tuned)
        ckpt_stage2 = Path(r"C:\coding\sih\model2_grounding\checkpoints\stage2_final.pth")
        ckpt_stage1 = Path(r"C:\coding\sih\model2_grounding\checkpoints\stage1_final.pth")
        if ckpt_stage2.exists():
            # Stage2 fine-tuned is preferred for inference if available
            pass  # keep pretrained for base; actual stage2 loading would be separate
        return str(cfg), str(w)
    s = get_settings()
    cfg = Path(s.gdino_config)
    w = Path(s.gdino_weights)
    pre = Path(s.pretrained_dir)
    if not cfg.exists() and (pre / "gdino_swinb.cfg").exists():
        cfg = pre / "gdino_swinb.cfg"
    if not w.exists() and (pre / "gdino_swinb.pth").exists():
        w = pre / "gdino_swinb.pth"
    # Absolute fallback to real repo
    if not Path(cfg).exists():
        cfg = Path(r"C:\coding\sih\model2_grounding\pretrained\GroundingDINO_SwinT_OGC.py")
    if not Path(w).exists():
        w = Path(r"C:\coding\sih\model2_grounding\pretrained\groundingdino_swint_ogc.pth")
    return str(cfg), str(w)


def _build_groundingdino_uncached():
    cfg_path, w_path = _resolve_gdino_paths()
    if not Path(cfg_path).exists():
        raise FileNotFoundError(f"GDINO config not found: {cfg_path} (set GDINO_CONFIG)")
    if not Path(w_path).exists():
        raise FileNotFoundError(f"GDINO weights not found: {w_path} (set GDINO_WEIGHTS)")
    # try real import via file location to avoid train name collision with model3
    try:
        import importlib.util as _ilu2
        _spec = _ilu2.spec_from_file_location("model2_train_build", _MODEL2_REPO / "train.py")
        _mod = _ilu2.module_from_spec(_spec)
        assert _spec.loader is not None
        _spec.loader.exec_module(_mod)  # type: ignore
        build_groundingdino = _mod.build_groundingdino
        device = torch.device("cuda" if (torch is not None and torch.cuda.is_available()) else "cpu") if torch is not None else "cpu"
        model = build_groundingdino(Path(cfg_path), Path(w_path), device)
        return model, device
    except Exception as e:
        raise RuntimeError(f"MODEL_LOAD_ERROR: GroundingDINO build failed: {e}") from e


def get_grounding_model():
    return manager.get("grounding_gdino", _build_groundingdino_uncached)


def run_grounding_inference(
    image_path: str | Path,
    query: str,
    conf_threshold: float = 0.35,
    image_size: int | None = None,
) -> Dict[str, Any]:
    """Real inference — boxes normalized [0,1] → pixel xyxy via H,W. Never invent bbox."""
    # Use real model2 config for size default if available
    if _MODEL2_AVAILABLE and _model2_cfg is not None:
        size = image_size or _model2_cfg.IMAGE_SIZE
    else:
        s = get_settings()
        size = image_size or s.image_size
    img_path = Path(image_path)
    # Directory S2 patch takes priority — real BigEarthNet patches are directories with B04 etc.
    # load_and_convert_s2 returns CHW tensor (3,H,W) — DO NOT add batch dim, run_inference does it
    if img_path.is_dir():
        image_tensor = load_and_convert_s2(img_path, size=size)  # CHW tensor
        if hasattr(image_tensor, "shape") and len(image_tensor.shape) == 3:
            _, h, w = image_tensor.shape
        else:
            h, w = size, size
        # keep CHW, no batch
    elif not img_path.exists():
        raise FileNotFoundError(f"Grounding image not found: {image_path}")
    else:
        # single file: load via PIL/rasterio
        if Image is None:
            raise RuntimeError("Pillow not installed")
        if rasterio is not None and img_path.suffix.lower() in (".tif", ".tiff"):
            image_tensor = load_and_convert_s2(img_path.parent, size=size)  # CHW tensor
            if hasattr(image_tensor, "shape") and len(image_tensor.shape) == 3:
                _, h, w = image_tensor.shape
            else:
                h, w = size, size
            # keep CHW
        else:
            pil = Image.open(img_path).convert("RGB")
            w, h = pil.size
            if size:
                pil = pil.resize((size, size), Image.BILINEAR)
                w, h = size, size
            arr = np.array(pil).astype(np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406]); std = np.array([0.229, 0.224, 0.225])
            arr = (arr - mean) / std
            image_tensor = torch.from_numpy(arr).permute(2, 0, 1).float() if torch is not None else arr  # CHW
            h, w = size, size

    try:
        model_tuple = get_grounding_model()
        model, device = model_tuple if isinstance(model_tuple, tuple) else (model_tuple, "cpu")
        import importlib.util as _ilu3
        _spec3 = _ilu3.spec_from_file_location("model2_train_run", _MODEL2_REPO / "train.py")
        _mod3 = _ilu3.module_from_spec(_spec3)
        assert _spec3.loader is not None
        _spec3.loader.exec_module(_mod3)  # type: ignore
        run_inference = _mod3.run_inference
        # Ensure image_tensor is CHW tensor normalized (from load_and_convert_s2)
        if isinstance(image_tensor, np.ndarray):
            # HWC → CHW
            import torch as _torch2
            if image_tensor.ndim == 3 and image_tensor.shape[2] == 3:
                image_tensor = _torch2.from_numpy(image_tensor).permute(2, 0, 1).float()
            else:
                image_tensor = _torch2.from_numpy(image_tensor).float()
        # run_inference returns boxes normalized [0,1], scores
        boxes, scores = run_inference(image_tensor, query, model, device, conf_threshold)
        # Convert to pixel xyxy exactly as reference: x1 = int(box[0].item() * W)
        H, W = h, w
        result_boxes = []
        result_scores = []
        for box, score in zip(boxes, scores):
            if hasattr(box, "tolist"):
                b = box.tolist()
                s_val = float(score.item() if hasattr(score, "item") else score)
            else:
                b = list(box)
                s_val = float(score)
            # b is [x0,y0,x1,y1] normalized or [cx,cy,w,h] normalized — handle both
            if len(b) == 4 and max(b) <= 1.5:  # normalized
                # assume cxcywh if reference used that; convert
                # GroundingDINO returns cxcywh normalized in some impls — check aspect
                # Heuristic: if w/h <1 and plausible cx, treat as cxcywh
                # Preserve reference: int(box[0].item() * W)
                # For safety support both: if box width >1 pixel equiv, treat as xyxy directly
                x1 = int(b[0] * W) if b[0] <= 1 else int(b[0])
                y1 = int(b[1] * H) if b[1] <= 1 else int(b[1])
                x2 = int(b[2] * W) if b[2] <= 1 else int(b[2])
                y2 = int(b[3] * H) if b[3] <= 1 else int(b[3])
                # if cxcywh, convert: x1 = (cx - w/2)*W
                if (x2 - x1) < W and (x1 < x2) and b[2] <= 1 and b[3] <= 1 and b[0] < 1:
                    # try cxcywh interpretation if width/height look like normalized wh
                    cx, cy, bw, bh = b
                    x1 = int((cx - bw/2) * W); y1 = int((cy - bh/2) * H)
                    x2 = int((cx + bw/2) * W); y2 = int((cy + bh/2) * H)
            else:
                x1, y1, x2, y2 = map(int, b[:4])
                s_val = float(score) if not hasattr(score, "item") else float(score.item())
            result_boxes.append([x1, y1, x2, y2])
            result_scores.append(s_val)
        if not result_boxes:
            return {"boxes": [], "scores": [], "bbox_xyxy": None, "bbox_normalized": None, "confidence": None}
        # primary box = highest score
        best_idx = int(np.argmax(result_scores))
        best_xyxy = result_boxes[best_idx]
        best_score = result_scores[best_idx]
        # normalized
        best_norm = [best_xyxy[0]/W, best_xyxy[1]/H, best_xyxy[2]/W, best_xyxy[3]/H]
        return {
            "boxes": result_boxes,
            "scores": result_scores,
            "bbox_xyxy": best_xyxy,
            "bbox_normalized": [round(float(v), 3) for v in best_norm],
            "confidence": float(best_score),
        }
    except FileNotFoundError:
        raise
    except RuntimeError as e:
        if "MODEL_LOAD_ERROR" in str(e):
            raise
        raise RuntimeError(f"MODEL_INFERENCE_ERROR: grounding failed: {e}") from e
    except Exception as e:
        raise RuntimeError(f"MODEL_INFERENCE_ERROR: grounding inference failed: {e}") from e


# ---------- Tool contract wrapper (§5) ----------

def grounding_tool(image_path: str, query: str, conf_threshold: float = 0.35) -> Dict[str, Any]:
    try:
        # Resolve path: RasterAsset may be minio_key or local storage
        p = Path(image_path)
        if not p.exists():
            # try orchestrator/storage fallback
            alt = Path("orchestrator/storage") / p.name
            if alt.exists():
                p = alt
            else:
                alt2 = Path("storage") / p.name
                if alt2.exists():
                    p = alt2
        if not p.exists() and not Path(str(p)).parent.exists():
            # still try as-is for S2 dir
            pass
        out = run_grounding_inference(str(p), query, conf_threshold=conf_threshold)
        if out["bbox_xyxy"] is None:
            # no detection is success with null confidence per rule 7
            return {
                "status": "success",
                "task": "grounding",
                "text": f"No target matching '{query}' detected.",
                "confidence": None,
                "artifacts": [],
                "metadata": {"detections": 0, "query": query, "image_path": str(p)},
            }
        art_path = str(Path("outputs/grounding") / f"{p.stem}_overlay.png")
        return {
            "status": "success",
            "task": "grounding",
            "text": f"Detected '{query}' with confidence {out['confidence']:.2f}. BBox {out['bbox_xyxy']} (normalized {out['bbox_normalized']}).",
            "confidence": float(out["confidence"]),
            "artifacts": [{"type": "bbox_overlay", "path": art_path, "bbox_xyxy": out["bbox_xyxy"], "bbox_normalized": out["bbox_normalized"]}],
            "metadata": {"boxes": out["boxes"], "scores": out["scores"], "query": query, "image_path": str(p)},
        }
    except FileNotFoundError as e:
        return {
            "status": "error",
            "task": "grounding",
            "error_code": "MODEL_LOAD_ERROR",
            "message": str(e),
            "retryable": False,
        }
    except RuntimeError as e:
        msg = str(e)
        code = "MODEL_LOAD_ERROR" if "MODEL_LOAD_ERROR" in msg else ("GPU_ERROR" if "CUDA" in msg or "gpu" in msg.lower() else "MODEL_INFERENCE_ERROR")
        return {
            "status": "error",
            "task": "grounding",
            "error_code": code,
            "message": msg,
            "retryable": code in ("MODEL_INFERENCE_ERROR", "GPU_ERROR", "TIMEOUT"),
        }
    except Exception as e:
        return {
            "status": "error",
            "task": "grounding",
            "error_code": "MODEL_INFERENCE_ERROR",
            "message": str(e)[:500],
            "retryable": True,
        }
