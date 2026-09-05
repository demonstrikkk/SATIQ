"""Agent: Task-Specific Router — Ollama qwen3.5:9b + real shims, no mocks."""
from __future__ import annotations
import time
import asyncio
import gc
from pathlib import Path
from typing import Any, Dict, List

from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import check_deadline_or_raise
from orchestrator.services.image_pipeline import resolve_asset
from orchestrator.capabilities.model_adapter import call_model

VRAM_SEMAPHORE = asyncio.Semaphore(2)
_VRAM_QUEUE = 0
_VRAM_QUEUE_LOCK = asyncio.Lock()

async def _vram_acquire():
    global _VRAM_QUEUE
    async with _VRAM_QUEUE_LOCK:
        _VRAM_QUEUE += 1
        queued = _VRAM_QUEUE
        from orchestrator.core.config import get_settings
        max_q = int(getattr(get_settings(), "vram_max_queue", 4))
        if queued > max_q + 2:  # +2 = semaphore permits
            _VRAM_QUEUE -= 1
            raise RuntimeError(f"VRAM_QUEUE_FULL: {queued} > {max_q}+2 — busy")
    return queued

async def _vram_release():
    global _VRAM_QUEUE
    async with _VRAM_QUEUE_LOCK:
        _VRAM_QUEUE = max(0, _VRAM_QUEUE - 1)

def _vram_queue_depth() -> int:
    return _VRAM_QUEUE

def _cleanup_vram():
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass
    try:
        gc.collect()
    except Exception:
        pass

async def task_agent_node(state: GraphState) -> GraphState:
    if state.get("is_cancelled") or state.get("cancel_requested"):
        state["error"] = "cancelled before VRAM acquire"
        state["error_type"] = "permanent"
        state["error_code"] = "cancelled"
        add_trace(state, "task_agent", "cancelled", {"reason": "abort before VRAM"}, latency_ms=0)
        return state
    check_deadline_or_raise(state.get("deadline_ms", 0), "task_agent")  # type: ignore
    try:
        from orchestrator.api.main import EXECUTIONS as _EXEC
        sid = state.get("session_id")
        if sid and _EXEC.get(sid, {}).get("is_cancelled"):
            state["error"] = "cancelled (EXECUTIONS flag)"
            state["error_type"] = "permanent"
            state["error_code"] = "cancelled"
            add_trace(state, "task_agent", "cancelled", {"reason": "EXECUTIONS.is_cancelled"}, latency_ms=0)
            return state
    except Exception:
        pass

    t0 = time.time()
    task_type = state.get("task_type", "vqa")
    query = state.get("query", "")
    assets = state.get("assets") or []
    image_ids = state.get("image_ids") or [a.get("asset_id") for a in assets if a.get("asset_id")]
    img_001 = image_ids[0] if len(image_ids) >= 1 else "img_001"
    img_t1 = image_ids[0] if len(image_ids) >= 1 else "img_2021"
    img_t2 = image_ids[1] if len(image_ids) >= 2 else "img_2023"
    optical_id = img_001
    sar_id = image_ids[1] if len(image_ids) >= 2 else "s1_001"
    if assets:
        opt = [a for a in assets if a.get("modality") in ("optical", "multispectral")]
        sar = [a for a in assets if a.get("modality") == "sar"]
        if opt:
            optical_id = opt[0].get("asset_id", optical_id)
        if sar:
            sar_id = sar[0].get("asset_id", sar_id)
        if len(assets) >= 2 and task_type == "change_vqa":
            img_t1 = assets[0].get("asset_id", img_t1)
            img_t2 = assets[1].get("asset_id", img_t2)

    def _resolve(aid: str) -> str:
        p = resolve_asset(aid)
        return str(p) if p else aid

    def _normalize(task: str, raw: Dict, q: str, ids: Dict[str, str]) -> Dict:
        text = raw.get("text") or raw.get("answer_text") or raw.get("answer") or ""
        conf = raw.get("confidence")
        arts = raw.get("artifacts") or raw.get("visual_artifacts") or []
        meta = raw.get("metadata") or {}
        base: Dict[str, Any] = {"task": task, "query": q, "answer_text": text, "confidence": conf, "artifacts": arts, "metadata": meta}
        base.update(ids)
        if task == "grounding":
            bbox_xyxy = raw.get("bbox_xyxy") or (arts[0].get("bbox_xyxy") if arts else None)
            bbox_norm = raw.get("bbox_normalized") or raw.get("bbox") or (arts[0].get("bbox_normalized") if arts else None)
            base.update({"bbox_xyxy": bbox_xyxy, "bbox_normalized": bbox_norm, "bbox": bbox_norm, "bbox_list": [bbox_xyxy] if bbox_xyxy else []})
            base["detected_label"] = meta.get("label") or meta.get("detected_label") or "target"
        if task == "optical_sar_fusion":
            base["per_modality_confidence"] = meta.get("per_modality_confidence") or raw.get("per_modality_confidence")
        return base

    async def _call_shim(task: str, q: str, paths: List[str]) -> Dict:
        if state.get("is_cancelled"):
            raise asyncio.CancelledError(f"abort before {task} shim")
        # P1 tool boundary: validate call before execution
        try:
            from orchestrator.helpers.tool_executor import validate_tool_call
            tool_map = {"vqa":"run_vqa","grounding":"run_grounding","change_vqa":"run_change_vqa","optical_sar_fusion":"run_fusion"}
            tname = tool_map.get(task, "run_vqa")
            targs = {"image_path": paths[0] if paths else "", "query": q} if task in ("vqa","grounding") else ({"image_t1": paths[0] if len(paths)>0 else "", "image_t2": paths[1] if len(paths)>1 else "", "query": q} if task=="change_vqa" else {"optical_path": paths[0] if len(paths)>0 else "", "sar_path": paths[1] if len(paths)>1 else "", "query": q})
            ok, why = validate_tool_call(tname, targs, {"session_id": state.get("session_id")})
            if not ok:
                raise RuntimeError(f"tool_call validation failed for {tname}: {why}")
        except RuntimeError:
            raise
        except Exception as e:
            # validation infra fail — do not block execution, just log
            state.setdefault("error_log", []).append(f"tool_call validator error: {e}")  # type: ignore
        queued = await _vram_acquire()
        try:
            if queued > 2:
                try:
                    from orchestrator.core.events import emit
                    sid = state.get("session_id")
                    if sid:
                        await emit(sid, "queue_position", {"position": queued - 2, "estimated_wait_ms": (queued - 2) * 6000})
                except Exception:
                    pass
            # Auto-reproject heterogenous CRS to EPSG:4326 (GAP-4) before shim — preserves radiometry via nearest
            resolved = [_resolve(p) for p in paths]
            try:
                crs_vals = [a.get("crs") for a in (assets or []) if a.get("crs")]
                if len(set(crs_vals)) > 1:
                    from orchestrator.services.tiling import reproject_to_target
                    reprojected = []
                    for rp in resolved:
                        try:
                            reprojected.append(reproject_to_target(rp, "EPSG:4326"))
                        except Exception:
                            reprojected.append(rp)
                    resolved = reprojected
                    state.setdefault("error_log", []).append(f"CRS heterogenous {crs_vals} -> reprojected to EPSG:4326")  # type: ignore
            except Exception:
                pass
            async with VRAM_SEMAPHORE:
                if state.get("is_cancelled"):
                    raise asyncio.CancelledError(f"abort after VRAM acquire {task}")
                try:
                    raw = await asyncio.to_thread(call_model, task, q, resolved)
                    # P1 result validator — never trust tool output as instruction
                    try:
                        from orchestrator.helpers.tool_executor import validate_tool_result
                        tool_map2 = {"vqa":"run_vqa","grounding":"run_grounding","change_vqa":"run_change_vqa","optical_sar_fusion":"run_fusion"}
                        tname2 = tool_map2.get(task, "run_vqa")
                        vok, vwhy = validate_tool_result(tname2, raw if isinstance(raw, dict) else {})
                        if not vok:
                            raise RuntimeError(f"tool_result validation failed for {tname2}: {vwhy}")
                    except RuntimeError:
                        raise
                    except Exception as e:
                        state.setdefault("error_log", []).append(f"tool_result validator error: {e}")  # type: ignore
                finally:
                    _cleanup_vram()
        finally:
            await _vram_release()
        # task-specific post
        if task == "grounding" and raw.get("bbox_normalized"):
            try:
                bn = [max(0.0, min(1.0, float(v))) for v in raw["bbox_normalized"]]
                raw["bbox_normalized"] = raw["bbox"] = bn
            except Exception:
                pass
        ids: Dict[str, str] = {}
        if task in ("vqa", "captioning", "grounding"):
            ids = {"image_id": paths[0] if paths else ""}
        elif task == "change_vqa":
            ids = {"image_t1_id": paths[0] if len(paths) > 0 else "", "image_t2_id": paths[1] if len(paths) > 1 else ""}
        elif task == "optical_sar_fusion":
            ids = {"optical_image_id": paths[0] if len(paths) > 0 else "", "sar_image_id": paths[1] if len(paths) > 1 else ""}
        res = _normalize(task, raw, q, ids)
        if task == "grounding" and res.get("bbox_normalized"):
            try:
                bn = res["bbox_normalized"]
                res["bbox_url"] = f"/api/assets/{paths[0]}?bbox={','.join(f'{v:.3f}' for v in bn)}&crs=EPSG:4326"
            except Exception:
                pass
        return res

    try:
        plan = state.get("plan") or {}
        sub_queries = plan.get("sub_queries") or state.get("sub_queries")
        # map task to image paths
        def _paths_for(task: str) -> List[str]:
            if task in ("vqa", "captioning", "grounding"):
                return [img_001]
            if task == "change_vqa":
                return [img_t1, img_t2]
            if task == "optical_sar_fusion":
                return [optical_id, sar_id]
            return [img_001]

        if sub_queries and isinstance(sub_queries, list) and len(sub_queries) > 1:
            from orchestrator.helpers.result_merger import merge_sub_results
            subs = [await _call_shim(task_type, sq, _paths_for(task_type)) for sq in sub_queries]
            out = merge_sub_results(subs)
            out["query"] = query
            out["task"] = task_type
        else:
            out = await _call_shim(task_type, query, _paths_for(task_type))

        state["task_output"] = out
        per_fused = None
        if isinstance(out.get("per_modality_confidence"), dict):
            per_fused = out["per_modality_confidence"].get("fused")
        state["confidence"] = out.get("confidence") if out.get("confidence") is not None else (per_fused if per_fused is not None else None)

        if task_type == "grounding" and out.get("bbox_xyxy"):
            try:
                bbox = out["bbox_xyxy"]
                geotiff_path = _resolve(img_001)
                crop_hint = f"crop_{state.get('session_id','')}_{bbox[0]}_{bbox[1]}.png"
                try:
                    from orchestrator.services.ffmpeg_preprocessor import FFmpegPreprocessor
                    p = Path(geotiff_path)
                    if p.exists() and p.suffix.lower() in (".tif", ".tiff", ".png", ".jpg", ".jpeg"):
                        crop_path = await FFmpegPreprocessor().crop_bbox_to_png(str(p), bbox, out_size=(512, 512))
                        state["last_crop_path"] = crop_path  # type: ignore
                        state.setdefault("tmp_files", []).append(crop_path)  # type: ignore
                    else:
                        raise FileNotFoundError(geotiff_path)
                except Exception:
                    state["last_crop_path"] = f"rs-processed/{state.get('session_id','')}/crop_{bbox[0]}_{bbox[1]}.png"  # type: ignore
                    state.setdefault("tmp_files", []).append(crop_hint)  # type: ignore
                label = out.get("detected_label") or "target"
                state.setdefault("entity_registry", {})[f"that {label}"] = f"bbox:{bbox}"  # type: ignore
                state.setdefault("coreference_map", {})[f"that {label}"] = f"bbox:{bbox}"  # type: ignore
            except Exception:
                pass

        if task_type == "change_vqa" and len(image_ids) >= 2:
            state["last_change_pair"] = [img_t1, img_t2]  # type: ignore

        if out.get("artifacts"):
            try:
                from orchestrator.tools.visualisation_tool import generate_visual_evidence
                img_paths = _paths_for(task_type)
                vis_out = generate_visual_evidence.invoke({"image_paths": img_paths, "model_output": out, "task": task_type}) if hasattr(generate_visual_evidence, "invoke") else {}
                if isinstance(vis_out, dict) and vis_out.get("artifacts"):
                    out["visual_artifacts"] = vis_out["artifacts"]
            except Exception:
                pass

        add_trace(state, "task_agent", "ok", {"task": task_type, "confidence": state["confidence"], "sub_queries": len(sub_queries) if sub_queries else 0, "has_numeric": out.get("answer_numeric") is not None, "artifacts": len(out.get("artifacts") or [])}, latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        msg = str(e)
        is_queue_full = "VRAM_QUEUE_FULL" in msg
        is_load_error = "MODEL_NOT_LINKED" in msg or "MODEL_LOAD_ERROR" in msg
        state["error"] = msg
        if is_queue_full:
            state["error_type"] = "permanent"
            state["error_code"] = "queue_full"
        else:
            state["error_type"] = "permanent" if is_load_error else "transient"
            state["error_code"] = "queue_full" if is_queue_full else ("MODEL_NOT_LINKED" if "MODEL_NOT_LINKED" in msg else ("MODEL_LOAD_ERROR" if is_load_error else ("MODEL_INFERENCE_ERROR" if "MODEL_INFERENCE_ERROR" in msg or "GPU_ERROR" in msg else "task_agent_failed")))
        state.setdefault("error_log", []).append(msg)  # type: ignore
        add_trace(state, "task_agent", "failed", {"error": msg, "error_code": state["error_code"]}, latency_ms=int((time.time()-t0)*1000))
    return state
