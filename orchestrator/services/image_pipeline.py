"""Single image resolver + streaming ingest helpers.

Replaces duplicated _resolve_asset_path in task_agents.py and api/main.py.
No hardcoded C:/Users/..., portable, content-hash aware.
"""
from __future__ import annotations
import re
import hashlib
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASES = [
    REPO_ROOT / "orchestrator" / "storage" / "ingest",
    REPO_ROOT / "orchestrator" / "storage",
    REPO_ROOT / "gateway" / "upload",
    REPO_ROOT / "outputs",
    Path.cwd() / "orchestrator" / "storage" / "ingest",
]


def sanitize_asset_id(asset_id: str) -> str:
    """Strip gateway prefixes and _yqm style suffixes."""
    raw = asset_id
    if raw.startswith("asset_"):
        raw = raw[len("asset_") :]
    # strip trailing _[a-z0-9] after extension
    raw = re.sub(r"(\.png|\.jpg|\.jpeg|\.tif|\.tiff|\.geotiff|\.gtiff|\.jp2)(_[a-zA-Z0-9]+)$", r"\1", raw)
    raw = re.sub(r"\.(png|jpg|jpeg|tif|tiff|geotiff|gtiff|jp2)_[a-zA-Z0-9]+$", r".\1", raw)
    return raw


def resolve_asset(asset_id: str, bases: List[Path] | None = None) -> Path | None:
    """Resolve asset_id to a real file Path, or None if not found.

    Search order:
      1. sanitized variants (asset_, file_, image- prefixes, timestamp extraction)
      2. each base directory (recursive via rglob for ingest)
      3. direct Path(asset_id) if absolute/relative exists
    No hardcoded Windows absolute fallback.
    """
    if not asset_id:
        return None
    clean = sanitize_asset_id(asset_id)
    # Build candidates
    cands: List[str] = []
    for cand in [asset_id, clean, Path(asset_id).name, Path(clean).name]:
        if cand not in cands:
            cands.append(cand)
    # file_ timestamp extraction: file_1788..._t1_rgb.png -> t1_rgb.png
    for c in list(cands):
        if c.startswith("file_") and "_" in c:
            parts = c.split("_")
            if len(parts) >= 3:
                meaningful = "_".join(parts[2:])
                if meaningful not in cands:
                    cands.append(meaningful)
                for ext in (".tif", ".png"):
                    stem = Path(meaningful).stem
                    cand2 = stem + ext
                    if cand2 not in cands:
                        cands.append(cand2)
            tail = c[len("file_") :]
            if tail not in cands:
                cands.append(tail)
        if c.startswith("image-"):
            tail = c[len("image-") :]
            if tail not in cands:
                cands.append(tail)

        # expand with extensions if missing
    expanded: List[str] = []
    for c in cands:
        expanded.append(c)
        if not Path(c).suffix:
            for ext in (".tif", ".tiff", ".geotiff", ".png", ".jpg", ".jp2"):
                cand2 = c + ext
                if cand2 not in expanded:
                    expanded.append(cand2)

    bases = bases or DEFAULT_BASES
    for cand in expanded:
        p = Path(cand)
        if p.is_absolute() and p.exists():
            return p
        for base in bases:
            try:
                direct = base / p.name if base.is_dir() else base / cand
                if direct.exists():
                    return direct
                # recursive search for ingest
                if "ingest" in str(base) and base.exists():
                    stem = Path(cand).stem
                    for ext in (".tif", ".tiff", ".geotiff", ".gtiff", ".jp2", ".png", ".jpg"):
                        for found in base.rglob(f"{stem}{ext}"):
                            if found.is_file():
                                return found
                    for found in base.rglob(Path(cand).name):
                        if found.exists():
                            return found
            except Exception:
                continue
        if Path(cand).exists():
            return Path(cand)
    return None


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def content_hash_path(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:16]
