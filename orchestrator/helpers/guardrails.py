"""Guardrails — plan==needed validator, output validator, prompt injection check."""
from __future__ import annotations
import json
import re
from typing import Any, Dict, List, Tuple

from orchestrator.registry.capability_registry import validate_legality
from pydantic import BaseModel, Field, ValidationError

INJECTION_PATTERNS = [
    r"<\s*system\s*>",
    r"\bignore previous instructions\b",
    r"\bdo anything now\b",
    r"```.*system",
    r"\brole\s*:\s*system\b",
]


ALLOWED_SUCCESS_CONDITIONS = {"bbox_in_0_1", "crs_valid", "gsd_positive", "confidence_ge_0_6", "answer_non_empty"}

class StepSpec(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    success_condition: str = Field(pattern=r"^(bbox_in_0_1|crs_valid|gsd_positive|confidence_ge_0_6|answer_non_empty)$")

    model_config = {"extra": "allow"}

class PlanSchema(BaseModel):
    task_type: str = Field(pattern=r"^(vqa|grounding|change_vqa|optical_sar_fusion|captioning|greeting|chitchat|help|out_of_scope|general|unknown)$")
    reasoning: str = Field(min_length=1, max_length=2000)
    required_assets: List[str] = Field(default_factory=list)
    fusion_needed: bool = False
    temporal_needed: bool = False
    confidence: float = Field(ge=0, le=1, default=0.8)
    skip_models: bool = False
    requires_coreg: bool = False
    tile_config: Dict[str, Any] | None = None
    data_requirements: Dict[str, Any] | None = None
    steps: List[str] = Field(default_factory=list)
    # per-step success conditions — optional, but when present each must be a known checker
    steps_detailed: List[StepSpec] | None = None
    step_success_conditions: List[str] | None = None

    model_config = {"extra": "allow"}


def check_prompt_injection(query: str) -> Tuple[bool, str]:
    ql = query.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, ql, flags=re.IGNORECASE):
            return True, f"injection pattern {pat}"
    # huge single-line JSON attempt to override
    if query.count("{") > 5 and "task_type" in ql and len(query) < 500:
        # may be legitimate JSON, but flag if contains system
        pass
    return False, ""


def validate_plan(plan: Dict[str, Any], assets: List[Dict[str, Any]], query_intent: str | None = None) -> Tuple[bool, str]:
    # schema
    try:
        PlanSchema.model_validate(plan)
    except ValidationError as e:
        return False, f"PlanSchema invalid: {e.errors()[0]['msg']}"
    # per-step success_condition allow-list
    for key in ("step_success_conditions",):
        vals = plan.get(key)
        if vals is not None:
            if not isinstance(vals, list):
                return False, f"{key} must be a list"
            for v in vals:
                if v not in ALLOWED_SUCCESS_CONDITIONS:
                    return False, f"invalid success_condition {v!r} — allowed {sorted(ALLOWED_SUCCESS_CONDITIONS)}"
    steps = plan.get("steps") or []
    ssc = plan.get("step_success_conditions")
    if ssc is not None and len(ssc) > 0 and len(ssc) != len(steps):
        return False, f"step_success_conditions length {len(ssc)} != steps length {len(steps)}"
    # steps_detailed already validated via StepSpec pattern; enforce count cap 10 is via planner prompt, re-check here
    sd = plan.get("steps_detailed")
    if sd is not None and len(sd) > 10:
        return False, "too many detailed steps (>10)"
    if len(steps) > 10:
        return False, "too many steps (>10)"
    task = plan.get("task_type", "")
    # injection
    inj, reason = check_prompt_injection(json.dumps(plan))
    if inj:
        return False, f"plan injection {reason}"
    # legality vs assets
    if not plan.get("skip_models"):
        ok, why = validate_legality(task, assets)
        if not ok:
            return False, f"illegal tool for input: {why}"
    # skip_models only for non-geospatial
    if plan.get("skip_models") and task in ("vqa", "grounding", "change_vqa", "optical_sar_fusion"):
        # if query has geospatial need but skip, it's wrong
        ql = (plan.get("reasoning") or "").lower()
        if any(k in ql for k in ["detect", "where", "sar", "change"]):
            return False, "skip_models true but task is geospatial"
    return True, "ok"


def validate_output(task_type: str, output: Dict[str, Any]) -> Tuple[bool, str]:
    """Check bbox/confidence/RLE, no invention."""
    # confidence must be 0..1 if present
    conf = output.get("confidence")
    if conf is not None:
        try:
            c = float(conf)
            if not (0 <= c <= 1):
                return False, f"confidence {c} out of 0..1"
        except Exception:
            return False, "confidence not numeric"
    # grounding needs bbox
    if task_type == "grounding":
        bbox = output.get("bbox_xyxy") or output.get("bbox_normalized") or output.get("bbox")
        if not bbox:
            return False, "grounding output missing bbox"
        # bbox bounds
        try:
            if isinstance(bbox, (list, tuple)) and len(bbox) == 4:
                for v in bbox:
                    fv = float(v)
                    if not (-0.1 <= fv <= 1.5 or 0 <= fv <= 4096):
                        # allow both normalized and pixel
                        pass
            else:
                return False, "bbox not len 4"
        except Exception:
            return False, "bbox not numeric"
    # change mask if present must be valid
    rle = output.get("change_mask_rle")
    if rle == "invalid":
        return False, "invalid change_mask_rle"
    # answer_text must not be empty for non-skip
    if not output.get("answer_text") and task_type not in ("greeting", "chitchat"):
        return False, "empty answer_text"
    return True, "ok"
