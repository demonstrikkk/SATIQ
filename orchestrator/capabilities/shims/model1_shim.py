"""Shim for model1 (VQA GeoChat-7B) — wraps run_inference.py without editing it.

Original: models/model1/run_inference.py exposes load_model() + ask_geochat(model,tokenizer,processor,image_path,question)
We ensure image_path is passed as-is (no resampling) and wrap str result to dict contract.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL1_ROOT = REPO_ROOT / "models" / "model1"

# Lazy singleton: do not load at import — only on first inference
_MODEL = None
_TOKENIZER = None
_PROCESSOR = None

def _ensure_model():
    global _MODEL, _TOKENIZER, _PROCESSOR
    if _MODEL is not None:
        return _MODEL, _TOKENIZER, _PROCESSOR
    # import original without modifying it
    sys.path.insert(0, str(MODEL1_ROOT))
    try:
        import run_inference as m1  # type: ignore
        # run_inference.load_model expects merged_model dir
        _MODEL, _TOKENIZER, _PROCESSOR = m1.load_model()
        return _MODEL, _TOKENIZER, _PROCESSOR
    finally:
        # keep path
        pass

def inference(image_path: str, query: str) -> Dict[str, Any]:
    """Contract: inference(image_path: str, query: str) -> dict {text, confidence, artifacts}"""
    if not image_path or not Path(image_path).exists():
        raise FileNotFoundError(f"Image not found for VQA: {image_path}")
    # Do NOT alter image — pass exact path
    sys.path.insert(0, str(MODEL1_ROOT))
    import run_inference as m1  # type: ignore
    model, tokenizer, processor = _ensure_model()
    # Use original ask_geochat — it handles PIL open + prompt
    text = m1.ask_geochat(model, tokenizer, processor, image_path, query)
    # GeoChat has no confidence → None (honest)
    return {
        "text": text,
        "answer_text": text,
        "confidence": None,
        "artifacts": [],
        "metadata": {"model": "model1_geochat7b", "image_path": image_path, "question": query},
    }
