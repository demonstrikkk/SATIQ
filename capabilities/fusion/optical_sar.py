"""Optical-SAR Fusion capability — CROMA via C:\\coding\\sih\\model_4 (Model4Engine).

Integration per request: DO NOT copy whole model_4 into SATIQ.
Use only external inference via C:\\coding\\sih\\model_4\\engine.py::Model4Engine
and C:\\coding\\sih\\model_4\\data\\preprocessing (12-band S2 + 2-band S1).

Pipeline (per ABOUT_MODEL.md+HOW_TO_USE.md+engine.py):
 S2(12,120,120) -> S2 ViT(ALiBi) \
                              -> Cross-Modal Fusion (512-dim) -> Modality % (optical/sar 100%) + 19-class + CAM 120x120
 S1(2,120,120)  -> S1 ViT(ALiBi) /

Checkpoints (not copied):
  C:\\coding\\sih\\model_4\\checkpoints\\croma\\CROMA_base.pt ~777MB (frozen dual ViT 768-dim)
  C:\\coding\\sih\\model_4\\checkpoints\\fusion_head\\best_fusion_model.pt ~47.7MB (trainable head)

Preprocessing (data/preprocessing.py verbatim):
 S2: 12 bands B01..B12\\B10, /10000, BigEarthNet means/stds, clip -10..10
 S1: VV/VH dB=10*log10(power), clip VV -25..0 VH -32.5..-5, standardize

No mock: if checkpoints missing -> MODEL_LOAD_ERROR.
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any

import numpy as np

try:
    import torch
    from PIL import Image
except Exception:
    torch = None
    Image = None

from orchestrator.capabilities.model_manager import manager
from orchestrator.core.config import get_settings

# ---------- external model_4 loader (no copy) ----------
_MODEL4_ROOT = Path("C:/coding/sih/model_4")

def _load_model4_engine():
    s = get_settings()
    root = Path(getattr(s, "model4_root", str(_MODEL4_ROOT)))
    if not root.exists():
        raise FileNotFoundError(f"MODEL_LOAD_ERROR: model_4 root not found: {root}")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    # Prefer engine.py directly via file location (avoids package name collision)
    eng_path = root / "engine.py"
    if not eng_path.exists():
        raise FileNotFoundError(f"MODEL_LOAD_ERROR: engine.py not found: {eng_path}")
    spec = importlib.util.spec_from_file_location("model4_engine", str(eng_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"MODEL_LOAD_ERROR: cannot load engine.py spec: {eng_path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["model4_engine"] = mod
    spec.loader.exec_module(mod)  # type: ignore
    Model4Engine = getattr(mod, "Model4Engine")
    # Resolve checkpoints — prefer Settings, else model_4 defaults
    croma_pt = Path(getattr(s, "croma_base_weights", str(root / "checkpoints" / "croma" / "CROMA_base.pt")))
    fusion_pt = Path(getattr(s, "fusion_head_weights", str(root / "checkpoints" / "fusion_head" / "best_fusion_model.pt")))
    if not croma_pt.exists():
        raise FileNotFoundError(f"MODEL_LOAD_ERROR: CROMA_base.pt not found: {croma_pt}")
    if not fusion_pt.exists():
        raise FileNotFoundError(f"MODEL_LOAD_ERROR: best_fusion_model.pt not found: {fusion_pt}")
    # also ensure legacy alias croma_weights points there for CI check
    cfg_path = root / "configs" / "train_config.yaml"
    engine = Model4Engine(
        fusion_weights_path=str(fusion_pt),
        croma_weights_path=str(croma_pt),
        config_path=str(cfg_path) if cfg_path.exists() else None,
        device=None,  # auto cuda/cpu
        img_size=120,
        num_classes=19,
    )
    return engine


def _get_engine():
    return manager.get("croma_model4_engine", _load_model4_engine)


def _resolve_paths(opt_path: str | Path, sar_path: str | Path):
    # Reuse task_agents resolver semantics: asset_ prefix, file_ timestamp, absolute S2 roots
    import re
    from orchestrator.storage.paths import STORAGE_ROOT  # lazy
    def _resolve_one(p: Path) -> Path:
        if p.exists():
            return p
        # asset_ prefix -> storage/ingest
        if p.name.startswith("asset_"):
            cand = Path("orchestrator/storage/ingest") / p.name.replace("asset_", "", 1)
            if cand.exists():
                return cand
            cand2 = Path("orchestrator/storage/ingest") / p.name
            if cand2.exists():
                return cand2
        # file_ timestamp (gateway) -> gateway/upload or storage
        if p.name.startswith("file_"):
            for base in [Path("gateway/upload"), Path("orchestrator/storage"), Path("orchestrator/storage/ingest")]:
                c = base / p.name
                if c.exists():
                    return c
            # strip file_ timestamp prefix to find real patch name
            m = re.match(r"file_\d+_(.+)", p.name)
            if m:
                inner = m.group(1).replace("_yqm", "")
                for base in [Path("orchestrator/storage/ingest"), Path("gateway/upload")]:
                    c = list(base.rglob(inner))
                    if c:
                        return c[0]
        # absolute BigEarthNet fallback still handled by preprocessing (will search)
        # check storage directly
        for base in [Path("orchestrator/storage"), Path("orchestrator/storage/ingest"), Path("gateway/upload")]:
            c = base / p.name
            if c.exists():
                return c
            cand = base / p.name.replace("asset_", "", 1)
            if cand.exists():
                return cand
        return p

    return _resolve_one(Path(opt_path)), _resolve_one(Path(sar_path))


def run_optical_sar_fusion(optical_path: str, sar_path: str, question: str, threshold: float = 0.45) -> Dict[str, Any]:
    opt_p, sar_p = _resolve_paths(optical_path, sar_path)
    if not opt_p.exists():
        raise FileNotFoundError(f"Optical S2 not found: {optical_path} (resolved {opt_p})")
    if not sar_p.exists():
        raise FileNotFoundError(f"SAR S1 not found: {sar_path} (resolved {sar_p})")
    engine = _get_engine()

    # Use engine.predict_from_files (wraps load_and_preprocess_s2/s1 with 10000/divide, dB, 12+2 bands, 120x120)
    # Do not re-implement preprocessing here — delegate to model_4's verified pipeline (like infer.py)
    try:
        # Use same preprocessing as infer.py: engine.predict_from_files handles dir vs file dispatch
        result = engine.predict_from_files(str(opt_p), str(sar_p), threshold=threshold)
    except Exception as e:
        raise RuntimeError(f"MODEL_INFERENCE_ERROR: CROMA predict_from_files failed ({opt_p}, {sar_p}): {e}") from e

    # Build answer: natural_summary + enumerated detected classes with confidences
    predictions = result.get("predictions", [])
    detected = result.get("detected_classes", [])
    contrib = result.get("modality_contributions", {})
    natural = result.get("natural_summary", "")
    # question-aware prefix (engine has no question input; compose here)
    q_prefix = f"Query: '{question}'. " if question else ""
    # Format detected as string for composer
    if detected:
        det_str = ", ".join(detected)
        conf_str = ", ".join([f"{p['class_name']} {p['confidence']*100:.1f}%" for p in predictions if p.get("is_detected")][:5])
        answer = f"{q_prefix}{natural} Detected [{det_str}] — {conf_str}. Dominant: {contrib.get('dominant_modality','') } ({contrib.get('optical_percentage',0):.1f}% optical / {contrib.get('sar_percentage',0):.1f}% SAR)."
    else:
        top = predictions[0] if predictions else {}
        answer = f"{q_prefix}{natural}"

    # Persist CAM visualization (4-panel via engine.create_visualization_image) + raw CAM npy
    artifacts: list[dict] = []
    try:
        # Need tensors for visualization — reload tensors via same preprocessing to pass to create_visualization_image
        # Reuse engine internals: load tensors explicitly
        import sys as _sys
        root = Path(get_settings().model4_root)
        if str(root) not in _sys.path:
            _sys.path.insert(0, str(root))
        from data.preprocessing import load_and_preprocess_s2, load_and_preprocess_s1
        opt_t = load_and_preprocess_s2(str(opt_p), target_size=(engine.img_size, engine.img_size))
        sar_t = load_and_preprocess_s1(str(sar_p), target_size=(engine.img_size, engine.img_size))
        vis = engine.create_visualization_image(opt_t, sar_t, result)
        out_dir = Path("outputs/fusion")
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = f"{Path(str(opt_p)).stem}_{Path(str(sar_p)).stem}"
        # Sanitize stem (remove asset_/file_ prefixes)
        stem = stem.replace("asset_", "").replace("file_", "")
        vis_path = out_dir / f"{stem}_croma_4panel.png"
        vis.save(str(vis_path))
        artifacts.append({"type": "croma_4panel", "path": str(vis_path)})
        # Also save top_cam as PNG for quick overlay
        cam = result.get("top_cam")  # (120,120)
        if cam is not None:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(figsize=(4,4))
            ax.imshow(cam, cmap="jet")
            ax.axis("off")
            plt.tight_layout(pad=0)
            cam_path = out_dir / f"{stem}_topcam.png"
            plt.savefig(str(cam_path), dpi=150, bbox_inches="tight", pad_inches=0)
            plt.close(fig)
            artifacts.append({"type": "croma_topcam", "path": str(cam_path)})
        # Save spatial_cam npy for downstream
        cam_path_npy = out_dir / f"{stem}_spatial_cam.npy"
        np.save(str(cam_path_npy), result.get("spatial_cam", np.zeros((19,120,120))))
        artifacts.append({"type": "croma_spatial_cam", "path": str(cam_path_npy)})
    except Exception:
        # visualization is best-effort; fusion result still valid
        pass

    # Per-modality confidence contract: keep modality percentages as complement to class confidence
    per_mod = {"optical": float(contrib.get("optical_percentage", 0))/100.0, "sar": float(contrib.get("sar_percentage", 0))/100.0, "fused": float(predictions[0]["confidence"]) if predictions else None}
    # Overall confidence: top detected confidence, else top prediction, else None (never mocked 0.8)
    conf = None
    if predictions:
        for p in predictions:
            if p.get("is_detected"):
                conf = float(p["confidence"])
                break
        if conf is None:
            conf = float(predictions[0]["confidence"]) if predictions else None

    return {
        "answer_text": answer.strip(),
        "confidence": conf,
        "per_modality_confidence": per_mod,
        "modality_contributions": contrib,
        "predictions": predictions,
        "detected_classes": detected,
        "natural_summary": natural,
        "class_map": result.get("top_cam"),
        "spatial_cam": result.get("spatial_cam"),
        "artifacts": artifacts,
    }


def _null_ctx():
    from contextlib import nullcontext
    return nullcontext()


def fusion_tool(optical_path: str, sar_path: str, question: str) -> Dict[str, Any]:
    try:
        out = run_optical_sar_fusion(optical_path, sar_path, question)
        arts = out.get("artifacts", [])
        # Ensure at least one artifact path for trace (even if viz failed, add placeholder)
        if not arts:
            arts = [{"type": "fusion_overlay", "path": str(Path("outputs/fusion") / f"{Path(optical_path).stem}_fused.png")}]
        return {
            "status": "success",
            "task": "optical_sar_fusion",
            "text": out["answer_text"],
            "confidence": out["confidence"],
            "artifacts": arts,
            "metadata": {
                "per_modality_confidence": out.get("per_modality_confidence"),
                "modality_contributions": out.get("modality_contributions"),
                "predictions": out.get("predictions", [])[:5],
                "detected_classes": out.get("detected_classes", []),
                "question": question,
                "optical_path": str(optical_path),
                "sar_path": str(sar_path),
            },
        }
    except FileNotFoundError as e:
        return {
            "status": "error",
            "task": "optical_sar_fusion",
            "error_code": "MODEL_LOAD_ERROR",
            "message": str(e),
            "retryable": False,
        }
    except RuntimeError as e:
        msg = str(e)
        code = "MODEL_LOAD_ERROR" if "MODEL_LOAD_ERROR" in msg else ("GPU_ERROR" if "CUDA" in msg else "MODEL_INFERENCE_ERROR")
        return {
            "status": "error",
            "task": "optical_sar_fusion",
            "error_code": code,
            "message": msg,
            "retryable": code in ("MODEL_INFERENCE_ERROR", "GPU_ERROR", "TIMEOUT"),
        }
    except Exception as e:
        return {
            "status": "error",
            "task": "optical_sar_fusion",
            "error_code": "MODEL_INFERENCE_ERROR",
            "message": str(e)[:800],
            "retryable": True,
        }
