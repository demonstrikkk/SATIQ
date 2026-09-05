# Model 2 — Grounding (GroundingDINO fine-tuned on BigEarthNet S2)

## What this module does

Given a **natural-language text query** and a **single optical satellite image**,
this model returns a **bounding box** (+ confidence score) localising the
described region. Example:

> Query: `"the water body in the north"`  
> Output: `[x1=0.12, y1=0.03, x2=0.45, y2=0.31]  score=0.71`

Architecture: **GroundingDINO** (Swin-T + BERT cross-attention, ~170M params).

---

## Quick Start

### 1. Install dependencies

```powershell
cd c:\coding\sih\model2_grounding

# Install PyTorch with CUDA 12.1 first
pip install torch==2.2.2 torchvision==0.17.2 --index-url https://download.pytorch.org/whl/cu121

# Then the rest
pip install -r requirements.txt

# GroundingDINO from source (compiles CUDA ops — takes ~5 min)
pip install git+https://github.com/IDEA-Research/GroundingDINO.git
```

### 2. Download pretrained weights

```powershell
# Weights only (Stage 1 BigEarthNet training)
python download_pretrained.py

# Weights + VRSBench (~15 GB, needed for Stage 2)
python download_pretrained.py --vrsbench
```

This downloads:
- `pretrained/groundingdino_swint_ogc.pth`  (~690 MB)
- `pretrained/GroundingDINO_SwinT_OGC.py`   (model config)
- BERT tokenizer cache (~430 MB)

---

## Training

### Stage 1 — BigEarthNet S2 pseudo-box warm-start (~5 epochs)

```powershell
python train.py --stage 1
```

- Reads B04/B03/B02 from your local `BigEarthNet-S2/` on the fly (no disk conversion)
- Converts BigEarthNet land-cover labels → referring expressions → whole-image pseudo-boxes
- Freezes Swin-T backbone; trains cross-modal fusion + box-regression head only
- Saves best checkpoint to `checkpoints/stage1_best.pth`

**Expected VRAM**: ~5.5 GB (fp16 + batch 2 + grad accum 4)  
**Expected time**: ~2–4 hours on a single RTX 3070/4060 Ti (8 GB)

### Stage 2 — VRSBench fine-tuning (~20 epochs)

```powershell
python train.py --stage 2 --resume checkpoints/stage1_best.pth
```

- Uses real referring-expression → bounding-box pairs from VRSBench
- Unfreezes last 2 Swin blocks in addition to fusion/decoder layers
- Saves best checkpoint to `checkpoints/stage2_best.pth`

**Expected VRAM**: ~6.5 GB (fp16 + batch 2 + grad accum 4)

### Quick smoke test (no training, just checks for errors / OOM)

```powershell
python train.py --stage 1 --max-steps 5 --dry-run
```

---

## Inference & Visualisation

```powershell
python visualize.py \
  --patch "c:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_27_57" \
  --query "the dense forest area" \
  --ckpt checkpoints/stage2_best.pth \
  --out result.png
```

---

## Dataset smoke tests

```powershell
# Test S2 on-the-fly RGB loading
python dataset.py --smoke-test

# Test VRSBench loading (if downloaded)
python dataset.py --smoke-test --vrsbench

# Test pseudo-box generation
python pseudo_boxes.py
```

---

## File map

| File | Purpose |
|---|---|
| `config.py` | All paths & hyperparameters |
| `download_pretrained.py` | Download weights + VRSBench |
| `pseudo_boxes.py` | Stage-1 label → pseudo-box conversion |
| `dataset.py` | On-the-fly S2 RGB + VRSBench datasets |
| `train.py` | Two-stage training loop |
| `visualize.py` | Inference + overlay visualisation |

---

## VRAM budget (8 GB GPU)

| Component | Memory |
|---|---|
| GroundingDINO Swin-T (fp16) | ~1.4 GB |
| Activations, batch=2, img=800px | ~2.8 GB |
| Gradients (trainable layers only) | ~1.2 GB |
| Optimiser states (AdamW) | ~0.8 GB |
| **Total** | **~6.2 GB** |

> Leaves ~1.8 GB headroom on an 8 GB card.  
> If you hit OOM: reduce `IMAGE_SIZE` to 640 in `config.py`, or lower `STAGE1_BATCH_SIZE` to 1.

---

## TensorBoard

```powershell
tensorboard --logdir c:\coding\sih\model2_grounding\runs
```
