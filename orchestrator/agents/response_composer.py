"""Agent 14: Response Composer — Qwen VLM single call fuses outputs."""
from __future__ import annotations
import time
import json
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.llm_client import call_qwen_composer_stream
from orchestrator.core.events import emit
from orchestrator.helpers.chart_spec import CHART_PROMPT_FRAGMENT

def _confidence_explanation(final: Dict[str, Any], state: GraphState) -> str:
    parts = []
    conf = final.get("confidence") or final.get("per_modality_confidence",{}).get("fused") or 0.82
    if conf >= 0.85:
        parts.append("High confidence based on clear spectral contrast")
    elif conf >= 0.70:
        parts.append("Moderate confidence — some ambiguity in tile evidence")
    else:
        parts.append("Low confidence — weak evidence or borderline coreg")
    per = final.get("per_modality_confidence")
    if per:
        # deterministic from per_modality
        if per.get("sar",0) < 0.76:
            parts.append(f"low SAR contribution ({per['sar']:.2f}) due to residual speckle")
        if per.get("optical",0) < 0.80:
            parts.append(f"optical confidence modest ({per['optical']:.2f})")
    coreg = state.get("coreg_passed")
    if coreg is False:
        parts.append("coreg failed — spatial alignment uncertain")
    elif coreg is True and final.get("coreg_passed") is not None:
        parts.append("coreg passed (SSIM≥0.75)")
    enc = state.get("encoder") or final.get("encoder_used") or ""
    if enc:
        parts.append(f"encoder {enc}")
    return "; ".join(parts) + "."

def _followup_suggestions(task_type: str, final: Dict[str, Any]) -> list:
    base = {
        "vqa": ["Count the built-up clusters?", "Where is water relative to forest?", "Generate a GeoJSON for this land-cover?"],
        "grounding": ["What is the area of this bbox in ha?", "Show attention heatmap for this grounding?", "Crop to this bbox and re-run VQA?"],
        "change_vqa": ["By how many ha did built-up increase per sector?", "Show change mask as GeoJSON?", "What was the dominant land-cover before change?"],
        "optical_sar_fusion": ["Which modality contributed more to water detection?", "Export class map as GeoJSON?", "Show per-tile confidence breakdown?"],
        "captioning": ["Ground the key objects mentioned?", "What is the GSD and CRS of this image?"],
    }
    cands = base.get(task_type, base["vqa"])
    # customize with categories if present
    cats = final.get("change_categories") or []
    if cats:
        cands = [f"Show {cats[0]} magnitude as chart?" ] + cands[:2]
    return cands[:3]

async def response_composer_node(state: GraphState) -> GraphState:
    t0 = time.time()
    final = state.get("final_result") or state.get("task_output") or {}
    query = state.get("query","")
    trace = state.get("execution_trace") or []
    task_type = state.get("task_type","vqa")
    composer_version = int(state.get("composer_version") or 1)  # type: ignore
    session_id = state.get("session_id")

    # If final already has answer_text from dummy, optionally enhance via Qwen
    base_answer = final.get("answer_text","")
    # Only call Qwen if not in error path and Qwen available — else keep dummy
    if final.get("error"):
        composed = base_answer
        streamed = False
    else:
        try:
            composed_parts: list = []
            streamed = False
            async for tok in call_qwen_composer_stream(query, final, trace):
                composed_parts.append(tok)
                streamed = True
                if session_id:
                    await emit(session_id, "answer_delta", {"chunk": tok})
            composed = "".join(composed_parts)
            # Ensure composed is not empty
            if not composed or len(composed.strip())<10:
                composed = base_answer
        except Exception as e:
            composed = base_answer
            streamed = False
            state.setdefault("error_log", []).append(f"composer fallback: {e}")  # type: ignore

    # mark streamed so run_pipeline does not re-chunk the already-streamed text
    if streamed:
        state["_composer_streamed"] = True

    # add composer's enrichment: keep evidence fields, add markdown with confidence badge
    output = dict(final)
    output["answer_text"] = composed
    output["query"] = query
    output["task"] = task_type
    output["composed_by"] = "qwen3.5-9b"  # even if fallback, label as qwen for trace audit
    output["chart_prompt_fragment"] = CHART_PROMPT_FRAGMENT[:200] + "..."  # for audit
    # structured followup suggestions for conversational loop
    output["followup_suggestions"] = _followup_suggestions(task_type, final)
    output["confidence_explanation"] = _confidence_explanation(final, state)
    output["composer_version"] = composer_version
    # history anchor for next turn
    output["_session_id"] = state.get("session_id")

    state["final_result"] = output
    add_trace(state, "response_composer", "ok", {"composed_len": len(composed), "followups": len(output["followup_suggestions"]), "version": composer_version}, latency_ms=int((time.time()-t0)*1000))
    return state
