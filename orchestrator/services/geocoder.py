"""Lightweight region name → bbox resolver. No external API — local admin boundaries GeoJSON lookup.

resolve_region_name(name, country_hint) -> bbox [minx,miny,maxx,maxy] WGS84 or None
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
import re

# Minimal built-in gazetteer for demo — covers regions mentioned in Satiq scenarios
BUILTIN_GAZETTEER: Dict[str, List[float]] = {
    # India admin examples
    "karnataka": [74.0, 11.5, 78.5, 18.5],
    "tamil nadu": [76.5, 8.0, 80.5, 13.5],
    "kerala": [74.5, 8.0, 77.5, 12.5],
    "delhi": [76.8, 28.4, 77.4, 28.9],
    "mumbai": [72.7, 18.9, 73.0, 19.3],
    "bengaluru": [77.4, 12.8, 77.7, 13.2],
    "chennai": [80.1, 12.9, 80.3, 13.2],
    "coastal": [79.5, 11.0, 81.0, 13.0],  # Tamil Nadu coast
    "northern region": [78.0, 15.0, 80.0, 18.0],
    "southern region": [76.0, 8.0, 78.0, 11.0],
    "eastern edge": [79.5, 12.0, 80.5, 13.0],
    "sector a": [79.0, 12.0, 79.5, 12.5],
    "sector b": [79.5, 12.0, 80.0, 12.5],
    "sector c": [80.0, 12.0, 80.5, 12.5],
}

GAZETTEER_PATH = Path("orchestrator/data/gazetteer.geojson")

def _load_geojson_gazetteer() -> Optional[Dict[str, Any]]:
    # optional external file
    candidates = [GAZETTEER_PATH, Path("data/gazetteer.geojson"), Path("orchestrator/storage/gazetteer.geojson")]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                continue
    return None

def resolve_region_name(name: str, country_hint: Optional[str] = None) -> Optional[List[float]]:
    """Resolve region name to WGS84 bbox. Case-insensitive substring match."""
    if not name or not name.strip():
        return None
    key = name.strip().lower()
    # direct builtin
    if key in BUILTIN_GAZETTEER:
        return BUILTIN_GAZETTEER[key]
    # substring match
    for k, bbox in BUILTIN_GAZETTEER.items():
        if key in k or k in key:
            return bbox
    # try geojson
    gj = _load_geojson_gazetteer()
    if gj:
        for feat in gj.get("features", []):
            props = feat.get("properties", {})
            fname = str(props.get("name","")).lower()
            if fname and (fname == key or key in fname or fname in key):
                geom = feat.get("geometry", {})
                # compute bbox from coordinates
                coords = geom.get("coordinates", [])
                try:
                    flat = []
                    def _collect(c):
                        if isinstance(c[0], (int,float)):
                            flat.append(c)
                        else:
                            for x in c:
                                _collect(x)
                    _collect(coords)
                    xs = [c[0] for c in flat]
                    ys = [c[1] for c in flat]
                    if xs and ys:
                        return [min(xs), min(ys), max(xs), max(ys)]
                except Exception:
                    continue
    # fallback: try geocoding via external API if available (disabled offline)
    return None

def resolve_from_query(query: str) -> Optional[Dict[str, Any]]:
    """Detect region name in query and resolve to bbox.
    Returns {region, bbox} or None.
    """
    from orchestrator.services.query_analyzer import detect_spatial_keywords
    sp = detect_spatial_keywords(query)
    region = sp.get("region")
    if not region:
        return None
    bbox = resolve_region_name(region)
    if bbox:
        return {"region": region, "bbox": bbox, "crs": "EPSG:4326"}
    return None

def list_known_regions() -> List[str]:
    return sorted(BUILTIN_GAZETTEER.keys())
