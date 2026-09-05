"""Shim for model4 (CROMA Fusion) — wraps infer.py/engine without editing.

Calls engine.predict on preprocessed tensors, no auto-discovery.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL4_ROOT = REPO_ROOT / "models" / "model4"

def inference(optical_path: str, sar_path: str, query: str) -> Dict[str, Any]:
    if not optical_path or not Path(optical_path).exists():
        raise FileNotFoundError(f"Optical not found: {optical_path}")
    if not sar_path or not Path(sar_path).exists():
        raise FileNotFoundError(f"SAR not found: {sar_path}")
    sys.path.insert(0, str(MODEL4_ROOT))
    from engine import Model4Engine  # type: ignore
    from data.preprocessing import load_and_preprocess_s2, load_and_preprocess_s1  # type: ignore
    engine = Model4Engine()
    opt_tensor = load_and_preprocess_s2(str(optical_path), target_size=(engine.img_size, engine.img_size))
    sar_tensor = load_and_preprocess_s1(str(sar_path), target_size=(engine.img_size, engine.img_size))
    result = engine.predict(opt_tensor, sar_tensor, threshold=0.45)
    # result has detected_classes, modality_contributions, natural_summary, predictions, spatial_cam
    text = result.get("natural_summary") or f"Detected {', '.join(result.get('detected_classes') or [])}"
    # confidence = top detected
    conf = None
    preds = result.get("predictions") or []
    if preds:
        det = [p for p in preds if p.get("is_detected")]
        if det:
            conf = float(det[0].get("confidence", 0))
        else:
            conf = float(preds[0].get("confidence", 0))
    # enrich query into text if query asks different
    if query and query.strip():
        text = f"{text} Query: {query}"
    return {
        "text": text,
        "answer_text": text,
        "confidence": conf,
        "per_modality_confidence": result.get("modality_contributions"),
        "detected_classes": result.get("detected_classes"),
        "predictions": preds,
        "spatial_cam": result.get("spatial_cam"),
        "artifacts": [
            {"type": "croma_4panel", "path": "outputs/fusion/croma_4panel.png"},
            {"type": "croma_spatial_cam", "path": "outputs/fusion/spatial_cam.npy"},
        ],
        "metadata": result,
    }
