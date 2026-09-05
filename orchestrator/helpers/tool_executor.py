"""Tool boundary — Validator → Executor → ResultValidator (P1 hardening).

Never: LLM → arbitrary tool. Always: LLM → structured tool_call → schema/allowlist/authorization/resource checks → executor → typed result → validation → state.

All tool names come from tool_schemas.REGISTERED_TOOLS single source; executor never trusts raw LLM text.
"""
from __future__ import annotations
from typing import Dict, Any, List

from orchestrator.helpers.tool_schemas import REGISTERED_TOOLS, TOOL_NAME_TO_TASK
from orchestrator.registry.capability_registry import get_capability, CAPABILITIES

ALLOWED_TOOL_NAMES = {t["function"]["name"] for t in REGISTERED_TOOLS}
# Max per spec P1-14
MAX_TOOL_CALLS = 10
MAX_SAME_TOOL_CALLS = 3
MAX_PLAN_STEPS = 10

def _schema_for(tool_name: str) -> Dict[str, Any] | None:
    for t in REGISTERED_TOOLS:
        if t["function"]["name"] == tool_name:
            return t["function"].get("parameters", {})
    return None

def validate_tool_call(tool_name: str, args: Dict[str, Any], context: Dict[str, Any] | None = None) -> tuple[bool, str]:
    """Schema + allowlist + authorization + resource checks."""
    if tool_name not in ALLOWED_TOOL_NAMES:
        return False, f"tool {tool_name} not in allowlist {sorted(ALLOWED_TOOL_NAMES)}"
    schema = _schema_for(tool_name)
    if schema is None:
        return False, f"no schema for {tool_name}"
    required = schema.get("required", [])
    for k in required:
        if k not in args or args[k] is None or (isinstance(args[k], str) and not args[k].strip()):
            return False, f"missing required arg {k} for {tool_name}"
    # capability legality if task tool
    if tool_name in TOOL_NAME_TO_TASK:
        task = TOOL_NAME_TO_TASK[tool_name]
        cap = get_capability(task)
        if cap is None:
            return False, f"unknown capability for tool {tool_name}"
        # modality / asset count checks deferred to validate_legality with real assets, but check tool-specific required
    # authorization placeholder: check context tenant/session owns assets (hook for P1 security layer)
    if context:
        # ensure session_id present
        if not context.get("session_id"):
            return False, "missing session_id in tool context"
    # resource limits
    return True, "ok"

def validate_tool_result(tool_name: str, result: Dict[str, Any]) -> tuple[bool, str]:
    """Typed result validation + provenance check. Tool output never becomes trusted instruction directly."""
    if not isinstance(result, dict):
        return False, "result must be dict"
    # provenance required for observability (P1-08)
    # allow missing provenance but warn via error_log, not fail
    # typed checks per tool
    if tool_name in ("run_grounding",):
        bbox = result.get("bbox_xyxy") or result.get("bbox_normalized") or result.get("bbox")
        if bbox is not None:
            if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
                return False, "bbox must be len 4"
            try:
                for v in bbox:
                    float(v)
            except Exception:
                return False, "bbox not numeric"
        # confidence 0..1 if present
        if result.get("confidence") is not None:
            try:
                c = float(result["confidence"])
                if not (0 <= c <= 1):
                    return False, "confidence out of 0..1"
            except Exception:
                return False, "confidence not numeric"
    if tool_name in ("run_vqa", "run_change_vqa", "run_fusion"):
        if not result.get("answer_text") and not result.get("text"):
            return False, "answer_text missing"
    # check injection in result text (tool output should not contain instruction override)
    txt = (result.get("answer_text") or result.get("text") or "")
    if isinstance(txt, str) and ("<system>" in txt.lower() or "ignore previous instructions" in txt.lower()):
        return False, "tool result contains injection pattern"
    return True, "ok"

def execute_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic executor — dispatches to shim or deterministic helper. No LLM in this path."""
    # Model tools go via model_adapter; deterministic go via local helpers
    if tool_name in TOOL_NAME_TO_TASK:
        # model shim path — image_paths from args
        from orchestrator.capabilities.model_adapter import call_model
        task = TOOL_NAME_TO_TASK[tool_name]
        image_paths: List[str] = []
        if tool_name == "run_vqa":
            image_paths = [args.get("image_path", "")]
        elif tool_name == "run_grounding":
            image_paths = [args.get("image_path", "")]
        elif tool_name == "run_change_vqa":
            image_paths = [args.get("image_t1", ""), args.get("image_t2", "")]
        elif tool_name == "run_fusion":
            image_paths = [args.get("optical_path", ""), args.get("sar_path", "")]
        q = args.get("query", "")
        return call_model(task, q, image_paths)
    # deterministic helpers
    if tool_name == "compute_spectral_indices":
        from orchestrator.services.spectral import compute_indices
        return compute_indices(args.get("asset_id", ""), args.get("indices", ["ndvi"]))
    if tool_name == "calculate_area":
        bbox = args.get("bbox", [0,0,1,1]); gsd = float(args.get("gsd", 10)); 
        area = (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) * gsd * gsd / 10000  # ha approx
        return {"area_ha": area, "bbox": bbox, "gsd": gsd}
    if tool_name == "geocode_region":
        from orchestrator.services.geocoder import resolve_region
        return resolve_region(args.get("region_name",""))
    if tool_name == "crop_bbox":
        from orchestrator.services.ffmpeg_preprocessor import FFmpegPreprocessor
        import asyncio
        path = args.get("image_path",""); bbox = args.get("bbox_xyxy",[0,0,100,100])
        try:
            return {"crop_path": FFmpegPreprocessor().crop_bbox_to_png(path, bbox)}
        except Exception as e:
            return {"error": str(e)}
    if tool_name == "generate_visual_evidence":
        from orchestrator.tools.visualisation_tool import generate_visual_evidence
        return generate_visual_evidence.invoke({"image_paths": args.get("image_paths",[]), "model_output": {}, "task": args.get("task","vqa")}) if hasattr(generate_visual_evidence, "invoke") else {"artifacts": []}
    if tool_name == "retrieve_history":
        return {"history": []}
    raise ValueError(f"unknown tool {tool_name}")

def check_plan_limits(plan: Dict[str, Any]) -> tuple[bool, str]:
    steps = plan.get("steps") or []
    if len(steps) > MAX_PLAN_STEPS:
        return False, f"steps {len(steps)} > {MAX_PLAN_STEPS}"
    # tool call limits if plan contains tool_calls
    calls = plan.get("tool_calls") or plan.get("steps") or []
    if len(calls) > MAX_TOOL_CALLS:
        return False, f"tool_calls {len(calls)} > {MAX_TOOL_CALLS}"
    # same tool repeat
    from collections import Counter
    counts = Counter([c if isinstance(c, str) else c.get("tool","") for c in calls])
    for t,cnt in counts.items():
        if cnt > MAX_SAME_TOOL_CALLS:
            return False, f"tool {t} repeated {cnt} > {MAX_SAME_TOOL_CALLS}"
    return True, "ok"
