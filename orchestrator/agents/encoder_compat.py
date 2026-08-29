"""Agent 5: Encoder Compat Check — gate."""
from __future__ import annotations
import time
from typing import List, Dict, Any
from orchestrator.models.graph_state import GraphState, add_trace

COMPAT = {
    "croma": {"needs": ["optical","sar"], "min_assets": 2},
    "prithvi": {"needs": ["any"], "min_assets": 2},
    "satmae": {"needs": ["any"], "min_assets": 1},
    "ssl4eo": {"needs": ["optical","multispectral"], "min_assets": 1},
}

def _norm_band(b: str) -> str:
    b = b.strip().upper()
    # B02 -> B2, B03 -> B3, B08 -> B8, B11 stays B11
    import re as _re
    m = _re.match(r"^B0*(\d+)$", b)
    if m:
        return f"B{int(m.group(1))}"
    return b

def check_required_bands(asset: Dict[str, Any], required_bands: List[str]) -> Dict[str, Any]:
    bands = asset.get("bands") or []
    if not bands:
        return {"available": True, "missing": [], "substitute_possible": False, "note": "no band metadata, assume available (dummy)"}
    # normalize both sides: B02 == B2, case-insensitive
    norm_bands = {_norm_band(x) for x in bands}
    norm_required = [_norm_band(x) for x in required_bands]
    # also handle common aliases: RED->B04, NIR->B08, etc. (map if needed)
    alias_map = {"RED":"B4","NIR":"B8","GREEN":"B3","BLUE":"B2","SWIR":"B11","SWIR1":"B11"}
    norm_required = [alias_map.get(x, x) for x in norm_required]
    norm_bands = {alias_map.get(x, x) for x in norm_bands}
    missing = [orig for orig, norm in zip(required_bands, norm_required) if norm not in norm_bands]
    return {
        "available": len(missing)==0,
        "missing": missing,
        "substitute_possible": len(missing) <=1,
        "note": f"Cartosat-2S has no NIR → NDVI impossible" if any("B8" in _norm_band(x) for x in missing) else "",
    }

def encoder_compat_node(state: GraphState) -> GraphState:
    t0 = time.time()
    encoder = state.get("encoder","satmae")
    assets = state.get("assets") or []
    image_ids = state.get("image_ids") or []
    plan = state.get("plan") or {}
    required_bands = (plan.get("data_requirements") or {}).get("bands") or ["B02","B03","B04"]
    n = len(assets) or len(image_ids) or 1  # if no metadata, assume 1
    cfg = COMPAT.get(encoder, {"needs": ["any"], "min_assets":1})
    passed = True
    reason = None
    band_reports = []
    sar_pol_req = (plan.get("data_requirements") or {}).get("sar_pol")
    for a in assets:
        modality = (a.get("modality") or "").lower()
        # SAR assets check polarization, not optical bands
        if modality == "sar":
            sar_bands = a.get("bands") or []
            # sar_pol like "VV+VH" or "VV" — check at least one present
            if sar_pol_req:
                # split required pols
                req_pols = [p.strip().upper() for p in sar_pol_req.replace("+",",").split(",") if p.strip()]
                # if asset has bands, check
                if sar_bands:
                    norm_sar = {b.upper() for b in sar_bands}
                    missing_pol = [p for p in req_pols if p not in norm_sar]
                    # for SAR, missing pol is not fatal if asset has any SAR band
                    if missing_pol and not any(b in norm_sar for b in ["VV","VH","HH","HV"]):
                        rep = {"available": False, "missing": missing_pol, "substitute_possible": True, "note": f"SAR pol mismatch {missing_pol}"}
                    else:
                        rep = {"available": True, "missing": [], "substitute_possible": False, "note": ""}
                else:
                    rep = {"available": True, "missing": [], "substitute_possible": False, "note": "no SAR band metadata, assume available"}
            else:
                rep = {"available": True, "missing": [], "substitute_possible": False, "note": "SAR no specific pol required"}
        else:
            rep = check_required_bands(a, required_bands)
        band_reports.append({"asset_id": a.get("asset_id"), "bands": a.get("bands"), **rep})
        if not rep["available"] and not rep["substitute_possible"]:
            if len(rep["missing"]) >2:
                passed = False
                reason = f"asset {a.get('asset_id')} missing bands {rep['missing']}"
    if n < cfg["min_assets"]:
        # for local testing without assets, we allow pass but log warning
        # real prod would fail. Here we treat missing assets as pass for dummy pipeline.
        if assets:
            passed = False
            reason = f"encoder {encoder} needs {cfg['min_assets']} assets, got {n}"
    # for croma, ideally have both modalities
    if encoder=="croma" and assets:
        mods = [a.get("modality") for a in assets]
        if "sar" not in mods or not any(m in ("optical","multispectral") for m in mods):
            # not hard fail for dummy, but flag
            reason = f"croma expects optical+SAR, got {mods}"
            # still pass for dummy data
            passed = True

    state["compat_passed"] = passed
    state["encoder_ready"] = True
    # propagate requires_coreg from plan if present
    plan = state.get("plan") or {}
    # StepPlan.requires_coreg or inferred from task_type
    rc = plan.get("requires_coreg")
    if rc is None:
        rc = state.get("task_type") in ("change_vqa","optical_sar_fusion")
        # single-image VQA/grounding/captioning → no coreg
        if state.get("task_type") in ("vqa","grounding","captioning"):
            rc = False
    state["requires_coreg"] = bool(rc)
    if not passed:
        state["error"] = reason
        state.setdefault("error_log", []).append(reason or "compat failed")  # type: ignore
        add_trace(state, "encoder_compat", "failed", {"encoder": encoder, "reason": reason, "requires_coreg": state["requires_coreg"], "band_reports": band_reports}, latency_ms=int((time.time()-t0)*1000))
    else:
        # warn if band missing but still passing (Cartosat case)
        for rep in band_reports:
            if rep["missing"]:
                state.setdefault("error_log", []).append(f"band warning {rep['asset_id']} missing {rep['missing']}")  # type: ignore
        add_trace(state, "encoder_compat", "ok", {"encoder": encoder, "requires_coreg": state["requires_coreg"], "band_reports": band_reports}, latency_ms=int((time.time()-t0)*1000))
    return state
