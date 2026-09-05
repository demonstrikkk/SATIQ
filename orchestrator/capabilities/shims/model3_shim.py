"""Shim for model3 (Change-VQA) — wraps visualize_index_hybrid.py without editing.

Uses hybrid path: compute_indices + classify_deltas + fusion_change_confidence + Vicuna text-only via build_prompt.
Requires BigEarthNet patch dirs or single image_paths that dataset._load_multispectral can handle.
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any
import sys
import torch

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL3_ROOT = REPO_ROOT / "models" / "model3"

def inference(image_t1: str, image_t2: str, query: str) -> Dict[str, Any]:
    if not image_t1 or not Path(image_t1).exists():
        raise FileNotFoundError(f"T1 not found: {image_t1}")
    if not image_t2 or not Path(image_t2).exists():
        raise FileNotFoundError(f"T2 not found: {image_t2}")
    sys.path.insert(0, str(MODEL3_ROOT))
    import config as cfg  # type: ignore
    from model import ChangeVQAModel  # type: ignore
    from dataset import BigEarthNetSyntheticCDVQADataset  # type: ignore
    from visualize_index_hybrid import compute_indices, classify_deltas, fusion_change_confidence, build_prompt, load_text_only_llm  # type: ignore
    from transformers import AutoTokenizer  # type: ignore

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    # Load stage1 fusion for confidence (if ckpt missing, confidence will be None handled)
    vqa_model = ChangeVQAModel(stage=1)
    vqa_model.vision_encoder.to(device)
    vqa_model.fusion.to(device)
    ckpt_path = Path(cfg.CHECKPOINT_DIR) / "stage1_final.pth" if hasattr(cfg, "CHECKPOINT_DIR") else MODEL3_ROOT / "checkpoints" / "stage1_final.pth"
    change_conf: float | None = None
    if ckpt_path.exists():
        ckpt = torch.load(str(ckpt_path), map_location=device)
        try:
            vqa_model.fusion.load_state_dict(ckpt["fusion"])
        except Exception:
            pass

    # Load multispectral via dataset helper (expects 6-band)
    tokenizer_dummy = AutoTokenizer.from_pretrained(cfg.LLM_DECODER) if hasattr(cfg, "LLM_DECODER") else AutoTokenizer.from_pretrained("lmsys/vicuna-7b-v1.5")
    dataset = BigEarthNetSyntheticCDVQADataset(tokenizer_dummy, max_samples=5)
    try:
        img_t1 = dataset._load_multispectral(Path(image_t1))
        img_t2 = dataset._load_multispectral(Path(image_t2))
    except Exception as e:
        # If single PNG, dataset may fail — fallback: treat as PIL and skip fusion, use indices only
        raise RuntimeError(f"MODEL_INFERENCE_ERROR: change _load_multispectral failed for {image_t1},{image_t2}: {e}")

    idx_t1 = compute_indices(img_t1)
    idx_t2 = compute_indices(img_t2)
    categories, deltas = classify_deltas(idx_t1, idx_t2, threshold=0.05)
    try:
        change_conf = fusion_change_confidence(vqa_model.vision_encoder, vqa_model.fusion, img_t1, img_t2, device)
    except Exception:
        change_conf = None

    # Build prompt and generate via Vicuna text-only
    prompt = build_prompt(categories, deltas, change_conf if change_conf is not None else 0.0)
    tokenizer, llm = load_text_only_llm(device)
    tokens = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        out = llm.generate(**tokens, max_new_tokens=60, do_sample=False, pad_token_id=tokenizer.eos_token_id)
    generated = tokenizer.decode(out[0], skip_special_tokens=True)
    answer = generated[len(prompt):].strip() if generated.startswith(prompt) else generated

    return {
        "text": answer,
        "answer_text": answer,
        "confidence": round(float(change_conf),3) if change_conf is not None else None,
        "change_categories": categories,
        "deltas": deltas,
        "artifacts": [],
        "metadata": {"categories": categories, "deltas": deltas, "prompt": prompt, "t1": image_t1, "t2": image_t2},
    }
