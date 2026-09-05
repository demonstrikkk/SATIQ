"""Vendored config for model2 GroundingDINO — minimal honest stub.

Mirrors expected attributes from original C:/coding/sih config:
IMAGE_SIZE, S2_PERCENTILE_LOW/HIGH, RGB_BANDS, INFERENCE_CONF_THRESHOLD,
PRETRAINED_DIR, GDINO_CONFIG/WEIGHTS, GDINO_CONFIG_FILES, GDINO_WEIGHT_FILES, MODEL_TYPE.
Fails closed: if pretrained weights missing, shim reports MODEL_NOT_LINKED.
"""
from pathlib import Path

IMAGE_SIZE = 224
S2_PERCENTILE_LOW = 2.0
S2_PERCENTILE_HIGH = 98.0
RGB_BANDS = ["B04", "B03", "B02"]  # Red, Green, Blue — Sentinel-2
INFERENCE_CONF_THRESHOLD = 0.35

# Relative pretrained — keep portable, no C:/ absolutes
PRETRAINED_DIR = Path(__file__).parent / "pretrained"
MODEL_TYPE = "swint_ogc"
GDINO_CONFIG = str(PRETRAINED_DIR / "GroundingDINO_SwinT_OGC.py")
GDINO_WEIGHTS = str(PRETRAINED_DIR / "groundingdino_swint_ogc.pth")

GDINO_CONFIG_FILES = {MODEL_TYPE: "GroundingDINO_SwinT_OGC.py", "swint_ogc": "GroundingDINO_SwinT_OGC.py"}
GDINO_WEIGHT_FILES = {MODEL_TYPE: "groundingdino_swint_ogc.pth", "swint_ogc": "groundingdino_swint_ogc.pth"}

CHECKPOINT_DIR = Path(__file__).parent / "checkpoints"
