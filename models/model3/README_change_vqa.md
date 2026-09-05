# Model 3: Change-VQA

This directory contains the training pipeline for the Change Visual-Question-Answering (Change-VQA) model, designed for a remote sensing multi-agent system.

## Architecture
- **Vision Encoder**: Prithvi-100M (IBM-NASA geospatial foundation model). Processes native multispectral data.
- **Temporal Fusion**: Transformer-based encoder (BIT/Changer style).
- **Projection Layer**: MLP mapping visual features to the LLM.
- **Language Decoder**: Vicuna-7B (4-bit QLoRA to fit in 8-12GB VRAM).

## Checkpoint Discipline
To conserve disk space and adhere to constraints, only the Fusion, Projection, and LoRA weights are saved during checkpointing. The base 7B LLM weights are never re-saved locally.

## Execution Steps

### 1. Download Pretrained Models & Datasets
First, download Prithvi-100M, initialize the Vicuna-7B tokenizer cache, and set up the CDVQA directory.
```powershell
python download_pretrained.py --models --cdvqa
```

### 2. Mandatory Parameter Verification
Before starting training, verify that the freeze/unfreeze logic correctly targets the intended layers.
```powershell
python print_param_names.py
```
**Expected Output**: Prithvi base layers should be frozen (requires_grad: False). The LoRA adapters (`q_proj`, `v_proj`) should be the only trainable layers in the LLM.

### 3. Stage 1: Representation Warm-Start
Stage 1 uses local BigEarthNet-S2 data. It freezes both Prithvi and the LLM, training only the fusion and projection layers via contrastive loss.
```powershell
python train.py --stage 1
```
*Note: Since BigEarthNet may lack true bi-temporal pairs, `pseudo_pairs.py` generates spatially-preserved augmentations (color jitter, etc.) to learn robust representations. No true VQA supervision happens here.*

### 4. Stage 2: Change-VQA Fine-Tuning
Stage 2 uses the CDVQA benchmark to fine-tune the LLM via LoRA along with the fusion and projection modules.
```powershell
python train.py --stage 2
```

### 5. Inference
Run inference to generate a JSON response describing changes.
```powershell
python visualize.py --img1 <path_t1> --img2 <path_t2> --question "What changed?" --ckpt checkpoints/stage2_final.pth
```
