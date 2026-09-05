"""
Hybrid Change-VQA inference -- WORKS TODAY WITHOUT STAGE 2 TRAINING.

WHY THIS EXISTS (read before using):
The direct pipeline (vis_embeds -> projection -> Vicuna inputs_embeds) produces
gibberish because the projection layer was only ever trained with a contrastive
loss (Stage 1) -- it has never been trained to output anything Vicuna's
embedding space actually understands. That alignment ONLY happens in Stage 2,
via a language-modeling loss on real question-answer pairs (CDVQA). There is
no way to skip that and still get meaningful vision-grounded text from Vicuna.

This script sidesteps the problem instead of pretending to solve it:
  1. Computes real, well-established remote-sensing change indices (NDVI,
     NDBI, NDWI) directly from the raw Sentinel-2 bands -- pure math, no
     trained model needed, reliable right now.
  2. Uses your TRAINED Stage 1 fusion module for what it actually learned --
     a "how different are these two scenes" signal (it was trained to tell
     true pairs from mismatched pairs, which is real change-sensitivity).
  3. Feeds the computed numbers to Vicuna as PLAIN TEXT ONLY -- no image
     embeddings, no projection layer in the loop at all. Vicuna's untouched
     pretrained language fluency turns the numbers into a real sentence.

This is a legitimate interim demo/plumbing path, not a replacement for Stage 2.
Once CDVQA is downloaded and Stage 2 is trained, switch back to visualize.py's
end-to-end multimodal path -- that's what actually lets the model "see" the
images, not just react to precomputed indices.
"""

import os
os.environ['HF_HUB_DISABLE_XET'] = '1'
import argparse
from pathlib import Path
import random

import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig

import config as cfg
from model import ChangeVQAModel
from dataset import BigEarthNetSyntheticCDVQADataset


# Band order per dataset._load_multispectral / tensor_to_rgb in visualize.py:
# 0=B02(Blue) 1=B03(Green) 2=B04(Red) 3=B8A(NIR) 4=B11(SWIR1) 5=B12(SWIR2)
BAND_IDX = {"blue": 0, "green": 1, "red": 2, "nir": 3, "swir1": 4, "swir2": 5}


def compute_indices(img):
    """
    img: (6, H, W) tensor, reflectance-normalized per Prithvi convention.
    Returns mean NDVI, NDBI, NDWI over the patch.
    """
    eps = 1e-6
    red = img[BAND_IDX["red"]]
    nir = img[BAND_IDX["nir"]]
    swir1 = img[BAND_IDX["swir1"]]
    green = img[BAND_IDX["green"]]

    ndvi = (nir - red) / (nir + red + eps)
    ndbi = (swir1 - nir) / (swir1 + nir + eps)
    ndwi = (green - nir) / (green + nir + eps)

    return {
        "ndvi": ndvi.mean().item(),
        "ndbi": ndbi.mean().item(),
        "ndwi": ndwi.mean().item(),
    }


def classify_deltas(idx_t1, idx_t2, threshold=0.05):
    """
    Turn raw index deltas into human-readable change categories using a
    fixed threshold. Threshold is a starting point -- tune against a few
    known before/after pairs if you have any ground truth to sanity-check.
    """
    deltas = {k: idx_t2[k] - idx_t1[k] for k in idx_t1}
    categories = []

    if deltas["ndvi"] < -threshold:
        categories.append("vegetation_loss")
    elif deltas["ndvi"] > threshold:
        categories.append("vegetation_gain")

    if deltas["ndbi"] > threshold:
        categories.append("built-up_increase")
    elif deltas["ndbi"] < -threshold:
        categories.append("built-up_decrease")

    if deltas["ndwi"] > threshold:
        categories.append("water_increase")
    elif deltas["ndwi"] < -threshold:
        categories.append("water_decrease")

    if not categories:
        categories.append("no_significant_change")

    return categories, deltas


@torch.no_grad()
def fusion_change_confidence(vision_encoder, fusion, img_t1, img_t2, device):
    """
    Uses the TRAINED Stage 1 fusion module to get a change-confidence score.
    Stage 1's contrastive objective taught it to separate true pairs from
    mismatched pairs -- so the spread/variance of its fused representation
    is a legitimate (if coarse) signal for "how much these two scenes differ",
    even though it was never trained to describe WHAT changed.
    """
    img_t1 = img_t1.unsqueeze(0).to(device)
    img_t2 = img_t2.unsqueeze(0).to(device)

    if img_t1.dim() == 4:
        img_t1_in = img_t1.unsqueeze(2).repeat(1, 1, 3, 1, 1)
        img_t2_in = img_t2.unsqueeze(2).repeat(1, 1, 3, 1, 1)
    else:
        img_t1_in, img_t2_in = img_t1, img_t2

    feat_t1 = vision_encoder.forward_features(img_t1_in)[-1]
    feat_t2 = vision_encoder.forward_features(img_t2_in)[-1]

    fused = fusion(feat_t1, feat_t2)  # (1, SeqLen*2, D)

    # Split back into the two halves post-fusion and measure how much the
    # fusion module pulled them apart/together in its learned space.
    seq_len = fused.shape[1] // 2
    fused_t1, fused_t2 = fused[:, :seq_len, :], fused[:, seq_len:, :]

    pooled_t1 = fused_t1.mean(dim=1)
    pooled_t2 = fused_t2.mean(dim=1)

    cos_sim = F.cosine_similarity(pooled_t1, pooled_t2).item()
    # cos_sim in [-1, 1]; map to a 0-1 "change confidence" (1 = very different)
    change_confidence = float((1.0 - cos_sim) / 2.0)
    return change_confidence


def build_prompt(categories, deltas, change_confidence):
    lines = [
        "You are a remote sensing analyst. Based ONLY on the numeric evidence "
        "below, write one concise sentence describing the land cover change "
        "between two Sentinel-2 satellite observations of the same area. "
        "Do not invent details not supported by the numbers.",
        "",
        f"NDVI change (vegetation index): {deltas['ndvi']:+.4f}",
        f"NDBI change (built-up index): {deltas['ndbi']:+.4f}",
        f"NDWI change (water index): {deltas['ndwi']:+.4f}",
        f"Detected change categories: {', '.join(categories)}",
        f"Overall change confidence (0=identical, 1=very different): {change_confidence:.2f}",
        "",
        "Summary:",
    ]
    return "\n".join(lines)


def load_text_only_llm(device):
    tokenizer = AutoTokenizer.from_pretrained(cfg.LLM_DECODER)
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    llm = AutoModelForCausalLM.from_pretrained(cfg.LLM_DECODER, quantization_config=bnb_config)
    # NOTE: no llm.to(device) here -- bitsandbytes 4-bit models are placed on
    # the correct device automatically by accelerate during from_pretrained().
    # Calling .to() on them is explicitly unsupported and raises ValueError.
    llm.eval()
    return tokenizer, llm


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", type=str, default=None)
    parser.add_argument("--t2", type=str, default=None)
    parser.add_argument("--threshold", type=float, default=0.05,
                         help="Index-delta threshold for flagging a category as changed.")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("--- Loading vision side (Prithvi encoder + trained Stage 1 fusion) ---")
    vqa_model = ChangeVQAModel(stage=1)  # stage=1 => no LLM built inside this object at all
    vqa_model.vision_encoder.to(device)
    vqa_model.fusion.to(device)

    stage1_ckpt = cfg.CHECKPOINT_DIR / "stage1_final.pth"
    if not stage1_ckpt.exists():
        raise FileNotFoundError(
            f"Stage 1 checkpoint not found at {stage1_ckpt}. This script needs your "
            f"trained fusion module -- run Stage 1 training first."
        )
    ckpt = torch.load(stage1_ckpt, map_location=device)
    vqa_model.fusion.load_state_dict(ckpt["fusion"])
    # Note: projection weights are NOT loaded here -- this script never uses
    # the projection layer, since its output space is exactly what's untrained
    # for language alignment. Only fusion is reused, for the confidence score.

    print("--- Loading dataset for patch access ---")
    tokenizer_dummy = None  # not needed for index computation
    dataset = BigEarthNetSyntheticCDVQADataset(AutoTokenizer.from_pretrained(cfg.LLM_DECODER), max_samples=100)

    if args.t1 and args.t2:
        img_t1 = dataset._load_multispectral(Path(args.t1))
        img_t2 = dataset._load_multispectral(Path(args.t2))
    else:
        idx = random.randint(0, len(dataset) - 1)
        img_t1, img_t2, _, _, _ = dataset[idx]

    print("--- Computing remote sensing indices (pure math, no trained model) ---")
    idx_t1 = compute_indices(img_t1)
    idx_t2 = compute_indices(img_t2)
    categories, deltas = classify_deltas(idx_t1, idx_t2, threshold=args.threshold)
    print(f"T1 indices: {idx_t1}")
    print(f"T2 indices: {idx_t2}")
    print(f"Deltas: {deltas}")
    print(f"Categories: {categories}")

    print("--- Computing change confidence from TRAINED Stage 1 fusion ---")
    change_confidence = fusion_change_confidence(
        vqa_model.vision_encoder, vqa_model.fusion, img_t1, img_t2, device
    )
    print(f"Fusion-based change confidence: {change_confidence:.3f}")

    print("--- Loading Vicuna for text-only summarization (no images involved here) ---")
    tokenizer, llm = load_text_only_llm(device)

    prompt = build_prompt(categories, deltas, change_confidence)
    print(f"\n--- Prompt sent to Vicuna ---\n{prompt}\n")

    tokens = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        output_ids = llm.generate(
            **tokens,
            max_new_tokens=60,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = tokenizer.decode(output_ids[0], skip_special_tokens=True)

    print("=" * 60)
    print("FINAL OUTPUT")
    print("=" * 60)
    print(generated)

    result = {
        "task": "change_vqa",
        "answer_text": generated[len(prompt):].strip() if generated.startswith(prompt) else generated,
        "change_categories": categories,
        "change_mask_rle": None,
        "confidence": round(change_confidence, 3),
    }
    print("\n--- Structured result (matches your API contract) ---")
    print(result)


if __name__ == "__main__":
    main()



"""
python visualize_index_hybrid.py --t1 "C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_43_57" --t2 "C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_42_73"
"""