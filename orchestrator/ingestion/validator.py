"""CRS hard gate — deterministic validator (also see agents/input_validator.py)."""
from __future__ import annotations
from typing import List, Dict, Any
from orchestrator.models.raster_asset import RasterAsset

def validate_crs_assets(assets: List[Dict[str,Any]]) -> tuple[bool, str | None]:
    """Returns (passed, error_msg). Hard fail on CRS mismatch."""
    crs_list = [a.get("crs") for a in assets if a.get("crs")]
    if len(set(crs_list)) > 1:
        return False, f"CRS mismatch: {crs_list}"
    # also reject missing CRS when multiple assets and pairing needed
    # but single image missing CRS is warning not fail — we allow for dummy
    return True, None

def validate_inputs(query: str, assets: List[Dict[str,Any]], image_ids: List[str]) -> tuple[bool, str | None]:
    if not query or not query.strip():
        return False, "query is required"
    if len(query) > 4000:
        return False, "query exceeds 4000 chars"
    ok, msg = validate_crs_assets(assets)
    if not ok:
        return False, msg
    # task vs config cross-check is done in router, not here
    return True, None

# Re-export for tests expecting validator.py
__all__ = ["validate_crs_assets","validate_inputs"]
