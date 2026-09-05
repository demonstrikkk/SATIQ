#!/usr/bin/env python3
"""Download Satiq model weights via huggingface_hub (single command).

Maps (do not edit inference scripts):
  model1 GeoChat-7B        -> liuhaotian/geochat-7b or thrivee/geochat-7b (HF) -> models/model1/merged_model
  model2 GroundingDINO B   -> IDEA-Research/grounding-dino-base            -> models/model2/pretrained
  model3 Prithvi-100M      -> ibm-nasa-geospatial/Prithvi-100M              -> models/model3/pretrained + checkpoints/stage1_final.pth
  model4 CROMA             -> MSCROMA/CROMA                                 -> models/model4/fusion/croma_base.pt

Usage:
  python scripts/download_weights.py --model all --dry-run
  python scripts/download_weights.py --model 1 --check
  HF_TOKEN=hf_xxx python scripts/download_weights.py --model all
  python scripts/download_weights.py --model all --output-dir models

Requires: huggingface_hub (pip install huggingface_hub hf_transfer), else falls back to listing URLs.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Mapping — repo_id → (local_dir relative to REPO_ROOT, friendly)
WEIGHT_MAP = {
    "1": {"repo": "liuhaotian/geochat-7b", "alt": "thrivee/geochat-7b", "local": "models/model1/merged_model", "files": ["config.json", "pytorch_model.bin", "tokenizer_config.json"]},
    "2": {"repo": "IDEA-Research/grounding-dino-base", "local": "models/model2/pretrained", "files": ["groundingdino_swint_ogc.pth"]},
    "3a": {"repo": "ibm-nasa-geospatial/Prithvi-100M", "local": "models/model3/pretrained", "files": ["Prithvi_100M.pt"]},
    "3b": {"repo": "ibm-nasa-geospatial/Prithvi-EO-2.0-300M-TL", "local": "models/model3/checkpoints", "files": ["stage1_final.pth"]},
    "4": {"repo": "MSCROMA/CROMA", "local": "models/model4/fusion", "files": ["croma_base.pt"]},
}

ALL_KEYS = ["1", "2", "3a", "3b", "4"]

def _hf_download(repo_id: str, local_dir: Path, dry_run: bool, check: bool) -> bool:
    if dry_run:
        print(f"  [dry-run] {repo_id} -> {local_dir}")
        return True
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or None
    try:
        from huggingface_hub import snapshot_download
        # enable hf_transfer if installed
        if "HF_HUB_ENABLE_HF_TRANSFER" not in os.environ:
            try:
                import hf_transfer  # noqa
                os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"
            except Exception:
                pass
        local_dir.mkdir(parents=True, exist_ok=True)
        print(f"[download] {repo_id} -> {local_dir} ...")
        snapshot_download(repo_id=repo_id, local_dir=str(local_dir), local_dir_use_symlinks=False, token=token, max_workers=4)
        print(f"  ✓ {repo_id}")
        return True
    except ImportError:
        print(f"  ✗ huggingface_hub not installed — pip install huggingface_hub hf_transfer, then rerun. URL: https://huggingface.co/{repo_id}")
        return False
    except Exception as e:
        msg = str(e)
        if "401" in msg or "403" in msg:
            print(f"  ✗ {repo_id} auth failed (set HF_TOKEN for gated repos): {msg[:200]}")
        elif "Repository Not Found" in msg:
            print(f"  ✗ {repo_id} not found — check alt repo: {msg[:200]}")
        else:
            print(f"  ✗ {repo_id} failed: {msg[:300]}")
        # fallback: try alt for geochat
        return False

def main():
    p = argparse.ArgumentParser(description="Satiq weight provisioner")
    p.add_argument("--model", default="all", help="all|1|2|3|4 or comma list e.g. 1,2")
    p.add_argument("--dry-run", action="store_true", help="list URLs without downloading")
    p.add_argument("--check", action="store_true", help="verify files exist then exit")
    p.add_argument("--output-dir", default=None, help="override models root (default models/)")
    args = p.parse_args()

    sel = []
    if args.model == "all":
        sel = ALL_KEYS
    else:
        for part in args.model.split(","):
            part = part.strip()
            if part == "3": sel.extend(["3a", "3b"])
            elif part in WEIGHT_MAP: sel.append(part)
            else: print(f"unknown model {part}, choose from 1,2,3,4,all"); sys.exit(1)

    if args.check:
        ok = True
        for k in sel:
            local = REPO_ROOT / WEIGHT_MAP[k]["local"]
            exists = local.exists() and any(local.iterdir()) if local.exists() else False
            status = "present" if exists else "absent - MODEL_NOT_LINKED"
            print(f"{k}: {local} -> {status}")
            if not exists: ok = False
        # also probe adapter
        try:
            sys.path.insert(0, str(REPO_ROOT))
            from orchestrator.capabilities.model_adapter import list_linked_models
            print("adapter:", list_linked_models())
        except Exception as e:
            print("adapter probe failed:", e)
        sys.exit(0 if ok else 1)

    # dry-run listing
    if args.dry_run:
        print("Dry-run — would download:")
        for k in sel:
            info = WEIGHT_MAP[k]
            print(f"  {k}: https://huggingface.co/{info['repo']} -> {REPO_ROOT / info['local']}")
        print("Set HF_TOKEN for gated repos, then run without --dry-run.")
        return

    # actual download
    for k in sel:
        info = WEIGHT_MAP[k]
        local = REPO_ROOT / info["local"]
        if args.output_dir:
            # override base: output-dir/model{k}/...
            local = REPO_ROOT / args.output_dir / Path(info["local"]).parts[-1] if len(sel)==1 else REPO_ROOT / args.output_dir
        _hf_download(info["repo"], local, dry_run=False, check=False)
        # geochat alt fallback
        if k == "1" and not any((REPO_ROOT / info["local"]).iterdir()) if (REPO_ROOT / info["local"]).exists() else True:
            if info.get("alt"):
                print(f"  trying alt {info['alt']} ...")
                _hf_download(info["alt"], local, dry_run=False, check=False)

    # final check
    print("\nPost-download check:")
    for k in sel:
        local = REPO_ROOT / WEIGHT_MAP[k]["local"]
        exists = local.exists() and any(local.iterdir()) if local.exists() else False
        print(f"  {k}: {local} -> {'present' if exists else 'absent - check HF_TOKEN'}")
    try:
        sys.path.insert(0, str(REPO_ROOT))
        from orchestrator.capabilities.model_adapter import list_linked_models
        print("adapter linked:", list_linked_models())
    except Exception:
        pass
    print("\nDone. If any absent, set HF_TOKEN and rerun. Then: docker compose up --build")

if __name__ == "__main__":
    main()
