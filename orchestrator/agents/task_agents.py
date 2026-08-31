"""Agent 10: Task-Specific Router — calls 4 REAL capability tools (no silent mock).

Per TASK PROMPT §1-§2: dummy_vqa/grounding/change_vqa/optical_sar_fusion replaced with
capabilities/single_image/vqa.py, grounding.py, temporal/change_vqa.py, fusion/optical_sar.py.
Each tool obeys §5 contract: success {status:success,...} or error {status:error, error_code, ...}.
If checkpoint missing → MODEL_LOAD_ERROR (never fake bbox/confidence).
Vision encoder/fusion nodes (satmae dummy) remain as shared fallback but capabilities now own their encoders.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

# Ensure repo root is on sys.path for top-level `capabilities.*` imports (SATIQ/capabilities)
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator.models.graph_state import GraphState, add_trace
from orchestrator.core.timeouts import check_deadline_or_raise
import importlib.util


def _load_tool_module(relative_path: str):
    full = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(relative_path.replace("/", ".").replace(".py", ""), full)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {relative_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod

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

    # Resolve asset paths: handles gateway upload (asset_*.png, file_*.png_yqm) → orchestrator/storage/ingest/*/*.tif
    # Frontend uploads via gateway/upload → gateway stores gateway/upload/{filename}, forwards to orchestrator ingest → orchestrator/storage/ingest/{stem}/{stem}.tif
    # This resolver searches all locations, strips asset_/file_ prefixes and _yqm-style suffixes, tries ingest recursive, and gateway fallback via HTTP fetch.
    def _resolve_asset_path(asset_id: str) -> str:
        import re
        # Strip asset_ prefix added by gateway upload.ts:22
        raw_id = asset_id
        if raw_id.startswith("asset_"):
            raw_id = raw_id[len("asset_"):]
        # Handle query-like suffixes: file_...png_yqm → file_...png (strip trailing _[a-z0-9]+ after extension)
        # Also handle _yqm, _abc etc appended after .png
        raw_id = re.sub(r"(\.png|\.jpg|\.jpeg|\.tif|\.tiff)(_[a-zA-Z0-9]+)$", r"\1", raw_id)
        asset_id_clean = re.sub(r"(\.png|\.jpg|\.jpeg|\.tif|\.tiff)(_[a-zA-Z0-9]+)$", r"\1", asset_id)
        # Fix raw string $ anchor (was \$) — ensure correct
        raw_id = re.sub(r"\.(png|jpg|jpeg|tif|tiff)_[a-zA-Z0-9]+$", r".\1", raw_id)
        asset_id_clean = re.sub(r"\.(png|jpg|jpeg|tif|tiff)_[a-zA-Z0-9]+$", r".\1", asset_id_clean)
        # Candidates to try: raw_id, asset_id, plus base names, plus stem without suffix
        cands = [asset_id, asset_id_clean, raw_id, Path(asset_id).name, Path(asset_id_clean).name, Path(raw_id).name]
        # Also try stem without _yqm and extract meaningful suffix for file_ timestamp files (e.g., file_1788181281160_t1_rgb.png -> t1_rgb.png)
        for c in list(cands):
            stem = Path(c).stem
            # stem may be file_...png -> handle _yqm already stripped, but also try without _yqm in stem
            stem_clean = re.sub(r"_[a-zA-Z0-9]+$", "", stem)
            if stem_clean != stem:
                cands.append(stem_clean + Path(c).suffix)
            # For file_ prefix with timestamp (file_1788181281160_t1_rgb), extract t1_rgb part
            if c.startswith("file_") and "_" in c:
                # file_1788181281160_t1_rgb.png -> t1_rgb.png
                parts = c.split("_")
                if len(parts) >= 3:
                    # parts[0]=file, parts[1]=1788181281160, parts[2:]=t1, rgb
                    meaningful = "_".join(parts[2:])
                    cands.append(meaningful)
                    cands.append(Path(meaningful).stem + ".tif")
                    cands.append(Path(meaningful).stem + ".png")
                # Also try without file_ prefix entirely
                cands.append(c[len("file_"):])
            if c.startswith("image-"):
                cands.append(c[len("image-"):])
            if c.startswith("asset_"):
                cands.append(c[len("asset_"):])
        # Expand with extensions
        expanded = []
        for c in cands:
            expanded.extend([c, f"{c}.tif", f"{Path(c).stem}.tif", f"{c}.png", f"{Path(c).stem}.png"])
        # Deduplicate
        seen = set()
        uniq = []
        for c in expanded:
            if c not in seen:
                seen.add(c)
                uniq.append(c)
        search_bases = [
            "orchestrator/storage", "storage",
            "gateway/upload", "gateway\\upload",
            "capabilities/single_image", "capabilities/fusion", "capabilities/temporal",
            ".",
        ]
        for cand in uniq:
            # Handle absolute Windows paths directly (S2 patch dirs like C:\coding\sih\...)
            if Path(cand).is_absolute():
                if Path(cand).exists():
                    return str(Path(cand))
                # Also try without drive letter funk
                continue
            for base in search_bases:
                p = Path(base) / cand
                if p.exists():
                    return str(p)
                # Also try recursive ingest: orchestrator/storage/ingest/**/cand (only for relative patterns)
                if base in ("orchestrator/storage", "storage"):
                    # Only use rglob with relative patterns (not absolute)
                    if not Path(cand).is_absolute():
                        try:
                            for found in Path(base).rglob(cand):
                                if found.exists():
                                    return str(found)
                        except ValueError:
                            # Non-relative pattern unsupported for rglob with Windows absolute path
                            pass
                        # Try stem match: find any .tif under ingest with same stem
                        stem = Path(cand).stem
                        try:
                            for found in Path(base).rglob(f"{stem}.tif"):
                                if found.is_file():
                                    return str(found)
                        except ValueError:
                            pass
                        # For S2 patch dirs that are directories, also try glob for the dir itself
                        try:
                            for found in Path(base).rglob(f"{stem}*"):
                                if found.exists() and found.is_dir():
                                    return str(found)
                        except ValueError:
                            pass
            # Direct path (handles absolute S2 patch dirs)
            if Path(cand).exists():
                return str(Path(cand))
            # Gateway static URL fallback: download to temp if gateway is running
            if cand.endswith(".png") or cand.endswith(".tif") or "." not in cand:
                for gw_base in ["http://127.0.0.1:4000", "http://localhost:4000"]:
                    try:
                        import urllib.request, tempfile, os
                        url = f"{gw_base}/api/assets/{Path(cand).name}"
                        # Quick check: try to fetch via gateway static serve
                        tmp = Path(tempfile.gettempdir()) / f"satiq_fetch_{Path(cand).name}"
                        if not tmp.exists():
                            try:
                                urllib.request.urlretrieve(url, tmp)
                                if tmp.exists() and tmp.stat().st_size > 0:
                                    return str(tmp)
                            except Exception:
                                pass
                        elif tmp.exists():
                            return str(tmp)
                    except Exception:
                        pass
        # Final fallback: search gateway/upload directly via absolute SATAQ path
        for cand in uniq:
            abs_gw = Path(r"C:\Users\aarav\Downloads\SATIQ\gateway\upload") / Path(cand).name
            if abs_gw.exists():
                return str(abs_gw)
            abs_gw2 = Path(r"C:\Users\aarav\Downloads\SATIQ\gateway/upload") / Path(cand).name
            if abs_gw2.exists():
                return str(abs_gw2)
        # Not found — return original id, capability will raise MODEL_LOAD_ERROR with clear message
        # Include hint for debugging
        return asset_id

    def _call_vqa(q: str, img: str):
        mod = _load_tool_module("capabilities/single_image/vqa.py")
        vqa_tool = mod.vqa_tool
        raw = vqa_tool(_resolve_asset_path(img), q)
        if raw["status"] == "error":
            raise RuntimeError(f"{raw['error_code']}: {raw['message']}")
        # Map tool contract → GraphState task_output shape expected downstream
        return {
            "task": "vqa", "query": q, "image_id": img,
            "answer_text": raw["text"], "confidence": raw["confidence"],
            "artifacts": raw.get("artifacts"), "metadata": raw.get("metadata"),
            "answer_type": "open", "answer_short": None,
        }

    def _call_grounding(q: str, img: str):
        mod = _load_tool_module("capabilities/single_image/grounding.py")
        grounding_tool = mod.grounding_tool
        raw = grounding_tool(_resolve_asset_path(img), q)
        if raw["status"] == "error":
            raise RuntimeError(f"{raw['error_code']}: {raw['message']}")
        art = (raw.get("artifacts") or [{}])[0] if raw.get("artifacts") else {}
        return {
            "task": "grounding", "query": q, "image_id": img,
            "answer_text": raw["text"], "confidence": raw["confidence"],
            "bbox_xyxy": art.get("bbox_xyxy"), "bbox_normalized": art.get("bbox_normalized"),
            "bbox": art.get("bbox_normalized"), "bbox_list": [art.get("bbox_xyxy")] if art.get("bbox_xyxy") else [],
            "artifacts": raw.get("artifacts"), "metadata": raw.get("metadata"),
            "detected_label": raw.get("metadata", {}).get("boxes", ["target"])[0] if isinstance(raw.get("metadata", {}).get("boxes"), list) else "target",
        }

    def _call_change_vqa(q: str, t1: str, t2: str):
        mod = _load_tool_module("capabilities/temporal/change_vqa.py")
        change_vqa_tool = mod.change_vqa_tool
        raw = change_vqa_tool(_resolve_asset_path(t1), _resolve_asset_path(t2), q)
        if raw["status"] == "error":
            raise RuntimeError(f"{raw['error_code']}: {raw['message']}")
        return {
            "task": "change_vqa", "query": q, "image_t1_id": t1, "image_t2_id": t2,
            "answer_text": raw["text"], "confidence": raw["confidence"],
            "change_categories": raw.get("metadata", {}).get("categories", []),
            "change_mask_rle": None, "artifacts": raw.get("artifacts"), "metadata": raw.get("metadata"),
            "pipeline_mode": raw.get("metadata", {}).get("pipeline_mode"),
        }

    def _call_fusion(q: str, opt: str, sar: str):
        mod = _load_tool_module("capabilities/fusion/optical_sar.py")
        fusion_tool = mod.fusion_tool
        raw = fusion_tool(_resolve_asset_path(opt), _resolve_asset_path(sar), q)
        if raw["status"] == "error":
            raise RuntimeError(f"{raw['error_code']}: {raw['message']}")
        return {
            "task": "optical_sar_fusion", "query": q, "optical_image_id": opt, "sar_image_id": sar,
            "answer_text": raw["text"], "confidence": raw["confidence"],
            "per_modality_confidence": raw.get("metadata", {}).get("per_modality_confidence"),
            "artifacts": raw.get("artifacts"), "metadata": raw.get("metadata"),
        }

    try:
        plan = state.get("plan") or {}
        sub_queries = plan.get("sub_queries") or state.get("sub_queries")
        # Multi-part handling via result_merger
        if sub_queries and isinstance(sub_queries, list) and len(sub_queries) > 1:
            from orchestrator.helpers.result_merger import merge_sub_results
            sub_results = []
            for sq in sub_queries:
                if task_type == "vqa" or task_type == "captioning":
                    r = _call_vqa(sq, img_001)
                elif task_type == "grounding":
                    r = _call_grounding(sq, img_001)
                elif task_type == "change_vqa":
                    r = _call_change_vqa(sq, img_t1, img_t2)
                elif task_type == "optical_sar_fusion":
                    r = _call_fusion(sq, optical_id, sar_id)
                else:
                    r = _call_vqa(sq, img_001)
                sub_results.append(r)
            out = merge_sub_results(sub_results)
            out["query"] = query
            out["task"] = task_type
        else:
            if task_type == "vqa" or task_type == "captioning":
                out = _call_vqa(query, img_001)
            elif task_type == "grounding":
                out = _call_grounding(query, img_001)
            elif task_type == "change_vqa":
                out = _call_change_vqa(query, img_t1, img_t2)
            elif task_type == "optical_sar_fusion":
                out = _call_fusion(query, optical_id, sar_id)
            else:
                out = _call_vqa(query, img_001)
        state["task_output"] = out
        # Confidence discipline rule 7: null stays null, never invent 0.82
        per_fused = None
        if isinstance(out.get("per_modality_confidence"), dict):
            per_fused = out["per_modality_confidence"].get("fused")
        state["confidence"] = out.get("confidence") if out.get("confidence") is not None else (per_fused if per_fused is not None else None)
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
        # Wire visualisation_tool for artifacts (grounding bbox overlay, change map)
        if out.get("artifacts"):
            try:
                from orchestrator.tools.visualisation_tool import generate_visual_evidence
                # invoke tool (sync) to ensure artifact paths registered
                img_paths = [img_001] if task_type in ("vqa","grounding") else ([img_t1, img_t2] if task_type=="change_vqa" else [optical_id, sar_id])
                # Note: generate_visual_evidence is a LangChain @tool; call directly via python function if available
                # We store returned artifact metadata in state for composer
                vis_out = generate_visual_evidence.invoke({"image_paths": img_paths, "model_output": out, "task": task_type}) if hasattr(generate_visual_evidence, "invoke") else {}
                if isinstance(vis_out, dict) and vis_out.get("artifacts"):
                    out["visual_artifacts"] = vis_out["artifacts"]
            except Exception:
                pass
        add_trace(state, "task_agent", "ok", {"task": task_type, "confidence": state["confidence"], "sub_queries": len(sub_queries) if sub_queries else 0, "has_numeric": out.get("answer_numeric") is not None, "artifacts": len(out.get("artifacts") or [])}, latency_ms=int((time.time()-t0)*1000))
    except Exception as e:
        msg = str(e)
        # Preserve error_code for error_handler retry semantics (§5): MODEL_LOAD_ERROR = permanent (retryable False), others transient
        is_load_error = "MODEL_LOAD_ERROR" in msg
        state["error"] = msg
        state["error_type"] = "permanent" if is_load_error else "transient"
        state["error_code"] = "MODEL_LOAD_ERROR" if is_load_error else ("MODEL_INFERENCE_ERROR" if "MODEL_INFERENCE_ERROR" in msg or "GPU_ERROR" in msg else "task_agent_failed")
        state.setdefault("error_log", []).append(msg)  # type: ignore
        add_trace(state, "task_agent", "failed", {"error": msg, "error_code": state["error_code"]}, latency_ms=int((time.time()-t0)*1000))
    return state
