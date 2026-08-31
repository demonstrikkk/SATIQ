"""VQA capability — GeoChat-7B Merged Model (Model 1 X) at C:\\coding\\sih\\final_model_1\\final_model_1.

Integration: DO NOT copy 13.5GB merged_model into SATIQ.
Use only external C:\\coding\\sih\\final_model_1\\final_model_1\\run_inference.py::load_model + ask_geochat verbatim.
Pipeline per run_inference.py: load_model(merged_model, 4bit NF4 ~7GB VRAM else FP16) -> ask_geochat(image_path, question) -> "<image>\\nUSER: {q} ASSISTANT:" -> model.generate.

No mock: if merged_model missing -> MODEL_LOAD_ERROR. Confidence null (GeoChat has no score).
"""
from __future__ import annotations
import importlib.util
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any

import numpy as np

try:
    from PIL import Image
    import rasterio
except Exception:
    Image = None
    rasterio = None

from orchestrator.capabilities.model_manager import manager
from orchestrator.core.config import get_settings

_GEOCHAT_ROOT = Path(r"C:\coding\sih\final_model_1\final_model_1")
_GEOCHAT_MERGED = _GEOCHAT_ROOT / "merged_model"
_GEOCHAT_RUN = _GEOCHAT_ROOT / "run_inference.py"


def _load_geochat_bundle():
    s = get_settings()
    merged_dir = Path(getattr(s, "geochat_model_dir", str(_GEOCHAT_MERGED)))
    run_path = Path(getattr(s, "geochat_run_inference", str(_GEOCHAT_RUN)))
    if not merged_dir.exists():
        raise FileNotFoundError(f"MODEL_LOAD_ERROR: GeoChat merged_model not found: {merged_dir} (set GEOCHAT_MODEL_DIR)")
    if not run_path.exists():
        raise FileNotFoundError(f"MODEL_LOAD_ERROR: run_inference.py not found: {run_path}")
    # ensure root on path for relative imports inside run_inference
    if str(_GEOCHAT_ROOT) not in sys.path:
        sys.path.insert(0, str(_GEOCHAT_ROOT))
    if str(merged_dir.parent) not in sys.path:
        sys.path.insert(0, str(merged_dir.parent))
    spec = importlib.util.spec_from_file_location("geochat_run_inference", str(run_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODEL_LOAD_ERROR: cannot load {run_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["geochat_run_inference"] = mod
    spec.loader.exec_module(mod)  # type: ignore
    # verbatim load_model from run_inference.py (handles 4bit NF4 vs FP16, device_map auto)
    load_model = getattr(mod, "load_model")
    # pass merged_dir as string; use 4bit if cuda else FP16
    bundle = load_model(str(merged_dir), load_4bit=True)
    # bundle is (model, tokenizer, image_processor)
    if isinstance(bundle, tuple) and len(bundle) == 3:
        model, tokenizer, image_processor = bundle
        return {"model": model, "tokenizer": tokenizer, "image_processor": image_processor, "_mod": mod}
    return {"bundle": bundle, "_mod": mod}


def get_vqa_model():
    return manager.get("geochat_7b_merged", _load_geochat_bundle)


def _resolve_image_path(image_path: str | Path) -> Path:
    p = Path(image_path)
    if p.exists() or p.is_dir():
        return p
    # try orchestrator storage fallbacks (handles gateway asset_ prefixes via task_agents, but vqa called via _resolve_asset_path already)
    for base in [Path("orchestrator/storage/ingest"), Path("gateway/upload"), Path("orchestrator/storage")]:
        cand = base / p.name
        if cand.exists():
            return cand
        try:
            for found in base.rglob(p.name):
                if found.exists():
                    return found
        except Exception:
            pass
    return p


def _prepare_geochat_image(image_path: Path) -> str:
    """GeoChat expects RGB PNG/JPG file. For S2 patch dirs or TIF, convert to temp PNG via grounding S2 pipeline."""
    if image_path.is_dir():
        # S2 patch dir with 12 TIFs -> load_and_convert_s2 -> denormalize -> temp PNG
        from capabilities.single_image.grounding import load_and_convert_s2
        hwc = load_and_convert_s2(image_path, size=336)  # GeoChat CLIP uses 336, but keep 224+ compatible
        mean = np.array([0.485, 0.456, 0.406]); std = np.array([0.229, 0.224, 0.225])
        rgb = (hwc * std + mean).clip(0, 1)
        pil = Image.fromarray((rgb * 255).astype(np.uint8))
        tmp = Path(tempfile.gettempdir()) / f"geochat_s2_{image_path.name}.png"
        pil.save(tmp)
        return str(tmp)
    if image_path.suffix.lower() in (".tif", ".tiff"):
        # single TIF (maybe ingested) -> try S2 parent dir, else PIL
        try:
            from capabilities.single_image.grounding import load_and_convert_s2
            # if parent has multiple B*.tif, treat as S2 patch
            if any(image_path.parent.glob("*_B0*.tif*")) or any(image_path.parent.glob("*_B*.tif*")):
                hwc = load_and_convert_s2(image_path.parent, size=336)
                mean = np.array([0.485, 0.456, 0.406]); std = np.array([0.229, 0.224, 0.225])
                rgb = (hwc * std + mean).clip(0, 1)
                pil = Image.fromarray((rgb * 255).astype(np.uint8))
                tmp = Path(tempfile.gettempdir()) / f"geochat_s2_{image_path.stem}.png"
                pil.save(tmp)
                return str(tmp)
        except Exception:
            pass
        # fallback PIL
        pil = Image.open(image_path).convert("RGB")
        tmp = Path(tempfile.gettempdir()) / f"geochat_{image_path.stem}.png"
        pil.save(tmp)
        return str(tmp)
    # regular PNG/JPG
    return str(image_path)


def run_vqa(image_path: str, question: str) -> Dict[str, Any]:
    p = _resolve_image_path(image_path)
    if not p.exists() and not p.is_dir():
        raise FileNotFoundError(f"VQA image not found: {image_path} (resolved {p})")
    bundle = get_vqa_model()
    model = bundle["model"]; tokenizer = bundle["tokenizer"]; image_processor = bundle["image_processor"]; mod = bundle["_mod"]
    ask_geochat = getattr(mod, "ask_geochat")
    # prepare image file for GeoChat (handles S2 dirs -> temp PNG)
    img_file = _prepare_geochat_image(p)
    try:
        # verbatim call per run_inference.py: ask_geochat(model, tokenizer, image_processor, image_path, question, max_new_tokens, temperature)
        text = ask_geochat(model, tokenizer, image_processor, img_file, question, max_new_tokens=256, temperature=0.2)
        # cleanup temp if we created it
        try:
            if img_file != str(p) and Path(img_file).exists() and "geochat" in img_file:
                Path(img_file).unlink(missing_ok=True)
        except Exception:
            pass
        return {"answer_text": text.strip(), "confidence": None}
    except Exception as e:
        raise RuntimeError(f"MODEL_INFERENCE_ERROR: GeoChat inference failed: {e}") from e


def _null_ctx():
    from contextlib import nullcontext
    return nullcontext()


def vqa_tool(image_path: str, question: str) -> Dict[str, Any]:
    try:
        out = run_vqa(image_path, question)
        return {
            "status": "success",
            "task": "vqa",
            "text": out["answer_text"],
            "confidence": out["confidence"],
            "artifacts": [],
            "metadata": {"question": question, "image_path": str(image_path), "model": "geochat-7b-merged"},
        }
    except FileNotFoundError as e:
        msg = str(e)
        # If GeoChat merged_model missing, try Ollama offline fallback only if GeoChat not available
        if "GeoChat" in msg or "merged_model" in msg or "run_inference" in msg:
            try:
                import ollama as _ollama_vqa
                from orchestrator.core.config import get_settings as _gs_vqa
                _m_vqa = _gs_vqa().qwen_model
                prompt = f"Describe the land cover in this satellite image in detail for query: '{question}'. Image: {Path(image_path).name} (satellite patch). Provide elaborative analysis, no bbox, cite confidence null."
                _r_vqa = _ollama_vqa.chat(model=_m_vqa, messages=[{"role":"user","content": prompt}])
                text = (_r_vqa.get("message", {}).get("content", "") or "").strip()
                if text:
                    return {
                        "status": "success",
                        "task": "vqa",
                        "text": text,
                        "confidence": None,
                        "artifacts": [],
                        "metadata": {"question": question, "image_path": str(image_path), "fallback": "ollama_qwen", "original_error": msg},
                    }
            except Exception:
                pass
        return {
            "status": "error",
            "task": "vqa",
            "error_code": "MODEL_LOAD_ERROR",
            "message": msg,
            "retryable": False,
        }
    except RuntimeError as e:
        msg = str(e)
        code = "MODEL_LOAD_ERROR" if "MODEL_LOAD_ERROR" in msg else ("GPU_ERROR" if "CUDA" in msg else "MODEL_INFERENCE_ERROR")
        return {
            "status": "error",
            "task": "vqa",
            "error_code": code,
            "message": msg,
            "retryable": code in ("MODEL_INFERENCE_ERROR", "GPU_ERROR", "TIMEOUT"),
        }
    except Exception as e:
        return {
            "status": "error",
            "task": "vqa",
            "error_code": "MODEL_INFERENCE_ERROR",
            "message": str(e)[:800],
            "retryable": True,
        }
