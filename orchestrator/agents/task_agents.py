"""Agent 10: Task-Specific Router — calls 4 dummy task functions."""
from __future__ import annotations
import time
from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.dummy.dummy_task_agents import dummy_vqa, dummy_grounding, dummy_change_vqa, dummy_optical_sar_fusion
from orchestrator.core.timeouts import check_deadline_or_raise

def task_agent_node(state: GraphState) -> GraphState:
    check_deadline_or_raise(state.get("deadline_ms", 0), "task_agent")  # type: ignore
    t0 = time.time()
    task_type = state.get("task_type","vqa")
    query = state.get("query","")
    fused = state.get("fused_repr") or {}
    # ids
    assets = state.get("assets") or []
    image_ids = state.get("image_ids") or [a.get("asset_id") for a in assets if a.get("asset_id")]
    # defaults
    img_001 = image_ids[0] if len(image_ids)>=1 else "img_001"
    img_t1 = image_ids[0] if len(image_ids)>=1 else "img_2021"
    img_t2 = image_ids[1] if len(image_ids)>=2 else "img_2023"
    optical_id = img_001
    sar_id = image_ids[1] if len(image_ids)>=2 else "s1_001"
    # if assets carry modality, pick accordingly
    if assets:
        optical_candidates = [a for a in assets if a.get("modality") in ("optical","multispectral")]
        sar_candidates = [a for a in assets if a.get("modality")=="sar"]
        if optical_candidates:
            optical_id = optical_candidates[0].get("asset_id", optical_id)
        if sar_candidates:
            sar_id = sar_candidates[0].get("asset_id", sar_id)
        if len(assets)>=2 and task_type=="change_vqa":
            img_t1 = assets[0].get("asset_id", img_t1)
            img_t2 = assets[1].get("asset_id", img_t2)

    try:
        plan = state.get("plan") or {}
        sub_queries = plan.get("sub_queries") or state.get("sub_queries")
        # Multi-part handling via result_merger
        if sub_queries and isinstance(sub_queries, list) and len(sub_queries) > 1:
            from orchestrator.helpers.result_merger import merge_sub_results
            sub_results = []
            for sq in sub_queries:
                if task_type == "vqa" or task_type == "captioning":
                    r = dummy_vqa(fused, sq, image_id=img_001)
                elif task_type == "grounding":
                    r = dummy_grounding(fused, sq, image_id=img_001)
                elif task_type == "change_vqa":
                    r = dummy_change_vqa(fused, sq, image_t1_id=img_t1, image_t2_id=img_t2)
                elif task_type == "optical_sar_fusion":
                    r = dummy_optical_sar_fusion(fused, sq, optical_image_id=optical_id, sar_image_id=sar_id)
                else:
                    r = dummy_vqa(fused, sq, image_id=img_001)
                sub_results.append(r)
            out = merge_sub_results(sub_results)
            out["query"] = query
            out["task"] = task_type
        else:
            if task_type == "vqa" or task_type == "captioning":
                out = dummy_vqa(fused, query, image_id=img_001)
            elif task_type == "grounding":
                out = dummy_grounding(fused, query, image_id=img_001)
            elif task_type == "change_vqa":
                out = dummy_change_vqa(fused, query, image_t1_id=img_t1, image_t2_id=img_t2)
            elif task_type == "optical_sar_fusion":
                out = dummy_optical_sar_fusion(fused, query, optical_image_id=optical_id, sar_image_id=sar_id)
            else:
                out = dummy_vqa(fused, query, image_id=img_001)
        state["task_output"] = out
        state["confidence"] = out.get("confidence") or out.get("per_modality_confidence", {}).get("fused") or 0.82
        # Phase C — FFmpeg crop for grounding: store bbox crop path for next-turn VQA
        if task_type == "grounding" and out.get("bbox_xyxy"):
            try:
                # store bbox for composer image:// and for next-turn coreference
                bbox = out["bbox_xyxy"]
                # minimal: record crop hint without requiring real GeoTIFF (dummy path)
                # real ffmpeg would be: crop_path = await FFmpegPreprocessor().crop_bbox_to_png(geotiff_path, bbox)
                crop_hint = f"crop_{state.get('session_id','')}_{bbox[0]}_{bbox[1]}.png"
                state["last_crop_path"] = f"rs-processed/{state.get('session_id','')}/crop_{bbox[0]}_{bbox[1]}.png"  # type: ignore
                state.setdefault("tmp_files", []).append(crop_hint)  # type: ignore
                # entity registry for coreference
                label = out.get("detected_label") or "target"
                state.setdefault("entity_registry", {})[f"that {label}"] = f"bbox:{bbox}"  # type: ignore
                state.setdefault("coreference_map", {})[f"that {label}"] = f"bbox:{bbox}"  # type: ignore
            except Exception:
                pass
        # Phase C — change VQA false-color hint
        if task_type == "change_vqa" and len(image_ids) >= 2:
            state["last_change_pair"] = [img_t1, img_t2]  # type: ignore
        add_trace(state, "task_agent", "ok", {"task": task_type, "confidence": state["confidence"], "sub_queries": len(sub_queries) if sub_queries else 0, "has_numeric": out.get("answer_numeric") is not None}, latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        state["error"] = str(e)
        state.setdefault("error_log", []).append(str(e))  # type: ignore
        add_trace(state, "task_agent", "failed", {"error": str(e)}, latency_ms=int((time.time()-t0)*1000))
    return state
