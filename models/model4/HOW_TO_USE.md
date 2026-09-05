# Guide: How to Use Model 4 (CROMA Optical–SAR Fusion)

This guide covers everything required to set up, load, run inference, and test Model 4.

---

## 1. Environment Setup

### Prerequisites
- Python 3.9, 3.10, 3.11, or 3.12
- PyTorch (CUDA recommended for GPU acceleration)

### Installation
```bash
# 1. Clone or extract model_4 package
cd model_4

# 2. Install dependencies
pip install -r requirements.txt

# 3. (Optional) Install PyTorch with CUDA if you have an NVIDIA GPU:
# pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

## 2. Quick Verification (Synthetic Demo Mode)

To verify the model weights, neural graph, and CAM pipeline without needing external GeoTIFF files:

```bash
python infer.py --demo
```

Output:
```
======================================================================
 SatQuery AI — Model 4: CROMA Multimodal Optical-SAR Fusion Engine
======================================================================
[Model 4] Initializing on device: cuda:0
[Model 4] Ready for inference.

=================================== RESULTS ===================================
Detected Classes (2):
  • Urban fabric
  • Arable land

Modality Contributions:
  • Sentinel-2 Optical: 64.2%
  • Sentinel-1 SAR:     35.8%
  • Dominant Modality:  OPTICAL

Natural Language Summary:
  "Multimodal satellite fusion identified: Urban fabric (91.4%), Arable land (78.2%). Prediction guided 64.2% by Sentinel-2 Optical reflectance and 35.8% by Sentinel-1 SAR radar backscatter."

[SAVED] 4-panel visual report saved to: inference_output.png
===============================================================================
```

---

## 3. Running CLI Inference on Real Satellite Files

```bash
# Run inference on Sentinel-2 and Sentinel-1 GeoTIFFs / folders
python infer.py \
    --optical /path/to/S2A_patch_folder_or_tif \
    --sar /path/to/S1A_patch_folder_or_tif \
    --threshold 0.45 \
    --output custom_report.png
```

---

## 4. Python SDK / Code Usage

You can easily import `Model4Engine` in your custom Python scripts or background workers:

```python
from engine import Model4Engine
import torch
import numpy as np

# 1. Initialize Engine (auto-loads checkpoints from checkpoints/)
engine = Model4Engine(device="cuda") # or "cpu"

# 2. Prepare or load input tensors
# Optical shape: (12, 120, 120), SAR shape: (2, 120, 120)
optical_tensor = np.random.randn(12, 120, 120).astype(np.float32)
sar_tensor = np.random.randn(2, 120, 120).astype(np.float32)

# 3. Predict
result = engine.predict(optical_tensor, sar_tensor, threshold=0.5)

# 4. Access outputs
print("Detected Classes:", result["detected_classes"])
print("Modality Contributions:", result["modality_contributions"])
print("Natural Summary:", result["natural_summary"])
print("Spatial CAM Array Shape:", result["spatial_cam"].shape) # (19, 120, 120)

# 5. Generate and save 4-panel visualization
image = engine.create_visualization_image(optical_tensor, sar_tensor, result)
image.save("analysis_report.png")
```

---

## 5. Starting the REST API Backend

Start the FastAPI microservice:
```bash
uvicorn api.fastapi_app:app --host 0.0.0.0 --port 8000
```

- Interactive Swagger Docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
