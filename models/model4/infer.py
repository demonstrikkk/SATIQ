#!/usr/bin/env python3
"""
Standalone CLI Inference Script for Model 4 (CROMA Optical-SAR Multimodal Fusion).

Automatically discovers Sentinel-1 SAR TIF files directly in the model_4 directory
and pairs them with corresponding or selected Sentinel-2 patches from BigEarthNet-S2.

Usage:
    # 1. Automatic auto-detection (finds S1 TIF in model_4 and matching/sample S2 patch in BigEarthNet-S2):
    python infer.py

    # 2. Explicit paths to GeoTIFF files or patch directories:
    python infer.py --optical C:/coding/sih/BigEarthNet-S2/S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP/S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_70_17 --sar S1A_IW_GRDH_1SDV_20170613T165108_33UUP_70_17_VV.tif

    # 3. Custom confidence threshold and output report filename:
    python infer.py --threshold 0.25 --output my_report.png

    # 4. Synthetic DEMO mode (no external data required):
    python infer.py --demo
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import torch

PACKAGE_ROOT = Path(__file__).resolve().parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from engine import Model4Engine
from data.preprocessing import load_and_preprocess_s2, load_and_preprocess_s1


def find_default_sar_file() -> Optional[Path]:
    """Find the first available Sentinel-1 GeoTIFF in the model_4 directory."""
    # Priority 1: Check for explicit S1 files in model_4 root
    s1_candidates = sorted(list(PACKAGE_ROOT.glob("*S1*.tif*")) + sorted(list(PACKAGE_ROOT.glob("*_VV.tif*"))))
    if s1_candidates:
        return s1_candidates[0]

    # Priority 2: Any .tif file in model_4 root
    all_tifs = sorted(list(PACKAGE_ROOT.glob("*.tif")) + list(PACKAGE_ROOT.glob("*.tiff")))
    if all_tifs:
        return all_tifs[0]

    return None


def find_matching_or_default_s2_patch(sar_file: Optional[Path] = None, s2_root: Optional[Path] = None) -> Optional[Path]:
    """
    Search for a Sentinel-2 patch in BigEarthNet-S2.
    If sar_file is provided, attempts to match the tile ID and coordinates (e.g. 33UUP_70_17).
    Otherwise returns the first valid patch folder found.
    """
    if s2_root is None:
        # Check standard possible locations for BigEarthNet-S2
        candidates = [
            PACKAGE_ROOT.parent / "BigEarthNet-S2",
            Path("C:/coding/sih/BigEarthNet-S2"),
            PACKAGE_ROOT / "data" / "BigEarthNet-S2"
        ]
        for c in candidates:
            if c.exists() and c.is_dir():
                s2_root = c
                break

    if not s2_root or not s2_root.exists():
        return None

    # Try matching tile coordinates if SAR filename is available
    if sar_file:
        sar_name = sar_file.name
        # Match pattern like 33UUP_70_17 or T33UUP_70_17
        match = re.search(r"(\d{2}[A-Z]{3}_\d+_\d+)", sar_name)
        if match:
            tag = match.group(1)
            # Look for subdirectories or patch folders containing this tag
            for acq_dir in s2_root.iterdir():
                if acq_dir.is_dir():
                    target_patch = acq_dir / f"S2A_MSIL2A_20170613T101031_N9999_R022_T{tag}"
                    if target_patch.exists() and target_patch.is_dir():
                        return target_patch
                    for p in acq_dir.glob(f"*{tag}*"):
                        if p.is_dir():
                            return p

    # Fallback: Find the first directory that contains S2 band .tif files
    for acq_dir in s2_root.iterdir():
        if acq_dir.is_dir():
            for patch_dir in acq_dir.iterdir():
                if patch_dir.is_dir() and any(patch_dir.glob("*_B0*.tif*")):
                    return patch_dir
            if any(acq_dir.glob("*_B0*.tif*")):
                return acq_dir

    return None


def main():
    parser = argparse.ArgumentParser(description="Model 4 Optical-SAR Multimodal Inference CLI")
    parser.add_argument("--optical", type=str, default=None, help="Path to Sentinel-2 patch directory or GeoTIFF (auto-detected if omitted)")
    parser.add_argument("--sar", type=str, default=None, help="Path to Sentinel-1 SAR GeoTIFF or directory (auto-detected if omitted)")
    parser.add_argument("--threshold", type=float, default=0.25, help="Confidence threshold (0.0 - 1.0, default: 0.25)")
    parser.add_argument("--output", type=str, default="inference_output.png", help="Path to save 4-panel visual report (default: inference_output.png)")
    parser.add_argument("--demo", action="store_true", help="Run with synthetic test tensors without external data")
    parser.add_argument("--device", type=str, default=None, help="Device: 'cuda' or 'cpu' (default: auto-detect)")
    parser.add_argument("--no-show", action="store_true", help="Disable displaying the visual report window")
    args = parser.parse_args()

    print("=" * 75)
    print(" SatQuery AI - Model 4: CROMA Multimodal Optical-SAR Fusion Engine")
    print("=" * 75)

    # Initialize Engine
    engine = Model4Engine(device=args.device)

    if args.demo:
        print("\n[INFO] Running in synthetic DEMO mode (generating sample random tensors)...")
        opt_tensor = torch.randn(12, engine.img_size, engine.img_size)
        sar_tensor = torch.randn(2, engine.img_size, engine.img_size)
        result = engine.predict(opt_tensor, sar_tensor, threshold=args.threshold)
    else:
        # Resolve SAR Path
        sar_path = Path(args.sar) if args.sar else find_default_sar_file()

        # Resolve Optical Path
        opt_path = None
        if args.optical:
            p = Path(args.optical)
            if p.is_dir() and not any(p.glob("*_B*.tif*")):
                # Passed a root directory like BigEarthNet-S2, find a patch inside
                opt_path = find_matching_or_default_s2_patch(sar_file=sar_path, s2_root=p)
            else:
                opt_path = p
        else:
            opt_path = find_matching_or_default_s2_patch(sar_file=sar_path)

        if not sar_path or not sar_path.exists():
            print(f"\n[ERROR] Sentinel-1 SAR input not found.")
            print(f"Please provide --sar /path/to/sar.tif or place a .tif in {PACKAGE_ROOT}")
            sys.exit(1)

        if not opt_path or not opt_path.exists():
            print(f"\n[ERROR] Sentinel-2 Optical input not found.")
            print(f"Please provide --optical /path/to/S2_patch or ensure BigEarthNet-S2 is accessible.")
            sys.exit(1)

        print(f"\n[INFO] Resolved Sentinel-1 SAR:     {sar_path}")
        print(f"[INFO] Resolved Sentinel-2 Optical: {opt_path}")

        print("\n[INFO] Preprocessing multispectral bands & radar backscatter...")
        opt_tensor = load_and_preprocess_s2(str(opt_path), target_size=(engine.img_size, engine.img_size))
        sar_tensor = load_and_preprocess_s1(str(sar_path), target_size=(engine.img_size, engine.img_size))

        print(f"[INFO] Running cross-attention multimodal fusion inference (threshold={args.threshold:.2f})...")
        result = engine.predict(opt_tensor, sar_tensor, threshold=args.threshold)

    # Print Formatted Results
    print("\n" + "=" * 33 + " RESULTS " + "=" * 33)
    print(f"Detected Classes ({len(result['detected_classes'])}):")
    if result["detected_classes"]:
        for cls in result["detected_classes"]:
            print(f"  [+] {cls}")
    else:
        print(f"  (None exceeded confidence threshold {args.threshold:.2f})")

    print("\nModality Contributions:")
    print(f"  - Sentinel-2 Optical: {result['modality_contributions']['optical_percentage']:.1f}%")
    print(f"  - Sentinel-1 SAR:     {result['modality_contributions']['sar_percentage']:.1f}%")
    print(f"  - Dominant Modality:  {result['modality_contributions']['dominant_modality'].upper()}")

    print("\nNatural Language Summary:")
    print(f"  \"{result['natural_summary']}\"")

    print("\nTop 5 Class Confidences:")
    for pred in result["predictions"][:5]:
        mark = "+" if pred["is_detected"] else " "
        print(f"  [{mark}] {pred['class_name']:<45} : {pred['confidence']*100:5.1f}%")

    # Generate, save, and display visual report
    if isinstance(opt_tensor, (torch.Tensor, np.ndarray)) and isinstance(sar_tensor, (torch.Tensor, np.ndarray)):
        vis_img = engine.create_visualization_image(opt_tensor, sar_tensor, result)
        out_file = Path(args.output)
        vis_img.save(str(out_file))
        print(f"\n[SAVED] 4-panel visual report saved to: {out_file.resolve()}")

        if not args.no_show:
            print("[INFO] Displaying inference visualization window...")
            try:
                vis_img.show(title="SatQuery AI - Model 4 Inference Report")
            except Exception as e:
                print(f"[NOTE] Display window: {e}")

    print("=" * 75)


if __name__ == "__main__":
    main()


