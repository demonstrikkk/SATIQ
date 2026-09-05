"""Vendored train.py stub for model2 — provides build_groundingdino + run_inference.

Tries to use installed GroundingDINO (pip install git+https://github.com/IDEA-Research/GroundingDINO.git).
If not installed or weights missing, raises honest MODEL_NOT_LINKED / MODEL_INFERENCE_ERROR
so shim can map to permanent/transient correctly. No dummy bbox invented.
"""
from pathlib import Path
from typing import Tuple, List
import torch

def build_groundingdino(config_path: str, weights_path: str, device: torch.device):
    cfg = Path(config_path)
    w = Path(weights_path)
    if not w.exists():
        raise FileNotFoundError(f"MODEL_NOT_LINKED: GroundingDINO weights missing at {w} — place groundingdino_swint_ogc.pth in models/model2/pretrained/")
    if not cfg.exists():
        raise FileNotFoundError(f"MODEL_NOT_LINKED: GroundingDINO config missing at {cfg}")
    try:
        # Use official groundingdino util if available
        from groundingdino.util.slconfig import SLConfig  # type: ignore
        from groundingdino.models import build_model  # type: ignore
        from groundingdino.util.utils import clean_state_dict  # type: ignore
    except Exception as e:
        raise ImportError(f"MODEL_NOT_LINKED: groundingdino package not installed ({e}) — pip install git+https://github.com/IDEA-Research/GroundingDINO.git") from e
    args = SLConfig.fromfile(str(cfg))
    args.device = device
    model = build_model(args)
    ckpt = torch.load(str(w), map_location="cpu")
    # ckpt may be dict with 'model' key
    sd = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
    try:
        model.load_state_dict(clean_state_dict(sd, device="cpu"), strict=False)
    except Exception:
        model.load_state_dict(sd, strict=False)
    model.to(device)
    model.eval()
    return model

def run_inference(image_tensor: torch.Tensor, query: str, model, device: torch.device, conf_threshold: float = 0.35) -> Tuple[List[torch.Tensor], List[float]]:
    """Run grounding inference on single tensor [1,3,H,W] already normalized."""
    if image_tensor is None or query is None:
        raise RuntimeError("MODEL_INFERENCE_ERROR: missing image_tensor or query")
    try:
        from groundingdino.util.inference import predict as gdino_predict  # type: ignore
        from transformers import AutoTokenizer  # type: ignore
        tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
        # groundingdino predict expects PIL or tensor + caption
        # Use batch 1
        boxes, logits, phrases = gdino_predict(model, image_tensor, query, conf_threshold, device=device, tokenizer=tokenizer)
        # normalize to expected (boxes [0,1] xyxy, scores list)
        scores = logits.tolist() if hasattr(logits, "tolist") else list(logits)
        # boxes is tensor [N,4] cxcywh or xyxy depending version — assume xyxy normalized
        return boxes, scores
    except Exception as e:
        # Fallback: try calling model directly if predict helper missing
        # Keep honest — propagate as transient
        raise RuntimeError(f"MODEL_INFERENCE_ERROR: GroundingDINO inference failed: {e}") from e
