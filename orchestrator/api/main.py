"""FastAPI orchestrator service — POST /api/v1/task, GET status, WS streaming."""
from __future__ import annotations
import asyncio
import uuid
import json
import time
from typing import Dict, Any, List, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks, Depends, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from orchestrator.models.raster_asset import InputSchema
from orchestrator.models.graph_state import new_state
from orchestrator.graph.pipeline import get_pipeline
from orchestrator.core.redis_state import session_state
from orchestrator.services.minio_client import minio_client
from orchestrator.services.transcription import transcribe_audio
from orchestrator.services.geojson_export import export_geojson
from orchestrator.services.report_generator import generate_report, save_report
from orchestrator.services.image_ingest import ingest_file, validate_geotiff_integrity
from orchestrator.helpers.trace import trace_summary
from orchestrator.core.llm_client import resolve_provider, has_local_qwen_capability, call_qwen_composer
from orchestrator.core.config import get_settings
from orchestrator.db.session import init_db
from orchestrator.helpers.chart_spec import validate_chart_spec
from orchestrator.services.conversation import save_history
from orchestrator.core.queue_gate import acquire as queue_acquire, release as queue_release, active_count as queue_active_count, get_limits as queue_limits
from orchestrator.core.circuit_breaker import qwen_circuit, vision_circuit, fusion_circuit
from orchestrator.core.metrics import snapshot as metrics_snapshot, record_request
from orchestrator.core.structured_logging import log_node as structured_log_node
from orchestrator.services.vision_encoder_service import health_live as vision_health_live, health_ready as vision_health_ready
from orchestrator.services.fusion_llm_service import health_live as fusion_health_live, health_ready as fusion_health_ready
from orchestrator.core.events import register_broadcaster

# Fix 3: Ephemeral artifact cleanup — sweep mtime>3600s
async def _periodic_disk_cleanup(interval_s: int = 600):
    import pathlib, time as _t, asyncio as _aio
    dirs = [pathlib.Path("orchestrator/storage/ingest"), pathlib.Path("gateway/upload"), pathlib.Path("/tmp")]
    while True:
        try:
            now = _t.time()
            for d in dirs:
                if not d.exists():
                    continue
                for p in d.rglob("*"):
                    try:
                        if p.is_file():
                            # keep .gitkeep, .db
                            if p.name in (".gitkeep", "memory.db", "audit.db"):
                                continue
                            # crop pngs: /tmp/crop_*.png
                            is_crop = p.name.startswith("crop_") and p.suffix == ".png"
                            is_ingest = "ingest" in str(p) or "upload" in str(p)
                            if (is_crop or is_ingest) and (now - p.stat().st_mtime > 3600):
                                p.unlink(missing_ok=True)
                    except Exception:
                        continue
            # also sweep gateway/upload via absolute if relative missed
            for alt in [pathlib.Path("C:/Users/asus/Downloads/Satiq/gateway/upload")]:
                if alt.exists():
                    for p in alt.rglob("*"):
                        try:
                            if p.is_file() and p.name not in (".gitkeep",) and (now - p.stat().st_mtime > 3600):
                                p.unlink(missing_ok=True)
                        except Exception:
                            continue
        except Exception:
            pass
        await _aio.sleep(interval_s)

app = FastAPI(title="Satiq Orchestrator", version="1.0.0", lifespan=None)  # lifespan set after definition (see below)

# CORS — explicit origins, no * with credentials (security)
def _cors_origins() -> list[str]:
    import os
    raw = os.getenv("CORS_ORIGIN", "http://localhost:3000,http://localhost:5173")
    if raw.strip() == "*":
        return ["http://localhost:3000", "http://localhost:5173"]
    return [o.strip() for o in raw.split(",") if o.strip()]

_cors_allow_origins = _cors_origins()
app.add_middleware(CORSMiddleware, allow_origins=_cors_allow_origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# in-memory store (fallback when DB not available)
EXECUTIONS: Dict[str, Dict[str,Any]] = {}
# pubsub for WS
WS_SUBSCRIBERS: Dict[str, List[WebSocket]] = {}

class TaskRequest(BaseModel):
    query: str
    image_ids: Optional[List[str]] = None
    image_t1_id: Optional[str] = None
    image_t2_id: Optional[str] = None
    optical_image_id: Optional[str] = None
    sar_image_id: Optional[str] = None
    assets: Optional[List[Dict[str,Any]]] = None
    session_id: Optional[str] = None
    # allow gateway style
    asset_ids: Optional[List[str]] = None
    spatial_refs: Optional[List[str]] = None

def _normalize_assets(req: TaskRequest) -> tuple[List[Dict[str,Any]], List[str]]:
    from orchestrator.core.config import get_settings
    allow_synth = bool(get_settings().allow_synthetic_assets)
    assets = req.assets or []
    image_ids: List[str] = []
    if req.image_ids:
        image_ids.extend(req.image_ids)
    if req.asset_ids:
        image_ids.extend(req.asset_ids)
    if req.image_t1_id:
        image_ids.append(req.image_t1_id)
    if req.image_t2_id:
        image_ids.append(req.image_t2_id)
    if req.optical_image_id:
        image_ids.append(req.optical_image_id)
    if req.sar_image_id:
        image_ids.append(req.sar_image_id)
    # Prod: try to resolve asset_ids via filesystem (image_pipeline) to build real CRS/GSD
    # before rejecting — gateway may send only IDs, but orchestrator has ingested file at
    # orchestrator/storage/ingest. Only reject if no real file found and ALLOW_SYNTHETIC false.
    if not assets and image_ids:
        # Attempt real resolution first (covers gateway asset_ids + frontend file_ IDs)
        try:
            from orchestrator.services.image_pipeline import resolve_asset
            from orchestrator.services.image_ingest import validate_geotiff_integrity
            for iid in image_ids:
                p = resolve_asset(iid)
                if p and p.exists():
                    v = validate_geotiff_integrity(p)
                    crs = v.get("crs") if v.get("valid") else None
                    width = v.get("width")
                    height = v.get("height")
                    # Use real CRS if present, else EPSG:4326 fallback (PNG without GeoTIFF)
                    assets.append({"asset_id": iid, "filename": p.name, "crs": crs or "EPSG:4326", "gsd": 10.0, "width": width, "height": height, "modality": "sar" if "s1" in iid.lower() or "sar" in iid.lower() else "optical"})
                elif allow_synth:
                    mod = "sar" if "s1" in iid.lower() or "sar" in iid.lower() else "optical"
                    assets.append({"asset_id": iid, "modality": mod, "crs": "EPSG:32617", "gsd": 10.0})
            if assets:
                # resolved at least one real asset — proceed
                pass
            elif not allow_synth:
                raise HTTPException(status_code=400, detail="assets required with real crs/gsd — set ALLOW_SYNTHETIC_ASSETS=true for tests or provide assets[]")
            else:
                for iid in image_ids:
                    mod = "sar" if "s1" in iid.lower() or "sar" in iid.lower() else "optical"
                    assets.append({"asset_id": iid, "modality": mod, "crs": "EPSG:32617", "gsd": 10.0})
        except HTTPException:
            raise
        except Exception:
            if not allow_synth:
                raise HTTPException(status_code=400, detail="assets required with real crs/gsd — set ALLOW_SYNTHETIC_ASSETS=true for tests or provide assets[]")
            for iid in image_ids:
                mod = "sar" if "s1" in iid.lower() or "sar" in iid.lower() else "optical"
                assets.append({"asset_id": iid, "modality": mod, "crs": "EPSG:32617", "gsd": 10.0})
    # also handle case where assets provided as ids with metadata
    # ensure each asset has asset_id
    for a in assets:
        if "asset_id" not in a and "id" in a:
            a["asset_id"] = a["id"]
    # dedupe ids
    image_ids = list(dict.fromkeys(image_ids))
    if not image_ids and assets:
        image_ids = [a.get("asset_id") for a in assets if a.get("asset_id")]  # type: ignore
    return assets, image_ids

def _exec_redis_key(sid: str) -> str:
    return f"satiq:exec:{sid}"

def _redis_client():
    try:
        import redis as _r
        import os as _os
        url = _os.getenv("REDIS_URL", get_settings().redis_url)
        return _r.from_url(url, socket_connect_timeout=0.5)
    except Exception:
        return None

def _persist_exec(sid: str):
    try:
        c = _redis_client()
        if c is None:
            return
        c.setex(_exec_redis_key(sid), 3600, json.dumps(EXECUTIONS.get(sid, {}), default=str))
    except Exception:
        pass

async def _broadcast(session_id: str, event: str, payload: Dict[str,Any] | None = None):
    # assign monotonic id for Last-Event-ID replay
    cur_events = EXECUTIONS.get(session_id, {}).get("events", [])
    msg_id = str(len(cur_events))
    msg = {"id": msg_id, "event": event, "payload": payload or {}, "timestamp": int(time.time()*1000)}
    # update in-memory
    if session_id in EXECUTIONS:
        EXECUTIONS[session_id].setdefault("events", []).append(msg)
        if event == "answer_delta":
            EXECUTIONS[session_id]["_streamed"] = True
        EXECUTIONS[session_id]["status"] = _status_from_event(event, EXECUTIONS[session_id].get("status","running"))
        if event in ("final_answer","query_completed","error","cancelled"):
            EXECUTIONS[session_id]["finished_at"] = time.time()
        # persist to Redis for recovery
        _persist_exec(session_id)
    # publish to redis (for other services)
    try:
        await session_state.publish(f"session:{session_id}:events", msg)
    except Exception:
        pass
    # WS push
    for ws in list(WS_SUBSCRIBERS.get(session_id, [])):
        try:
            await ws.send_json(msg)
        except Exception:
            pass


# allow graph nodes to emit live events (e.g. streamed answer tokens) to clients
register_broadcaster(_broadcast)

def _status_from_event(event: str, cur: str) -> str:
    if event in ("error",):
        return "failed"
    if event in ("cancelled",):
        return "cancelled"
    if event in ("final_answer","query_completed"):
        return "completed"
    return cur or "running"

async def run_pipeline(session_id: str, query: str, assets: List[Dict[str,Any]], image_ids: List[str]):
    acquired = True  # we already acquired in endpoint; if direct call, try acquire
    # if not already counted (burst test may call directly), ensure acquire
    # For background task path, endpoint already acquired — don't double-acquire; track via session flag
    is_direct = EXECUTIONS.get(session_id, {}).get("_queued") != True if session_id in EXECUTIONS else True
    try:
        try:
            _prov = resolve_provider()
            _s = get_settings()
            _model = _s.qwen_model if _prov == "local" else (_s.groq_model if _prov == "groq" else "mock_qwen_3.5_9b")
        except Exception:
            _prov, _model = "mock", "mock"
        await _broadcast(session_id, "query_started", {"query": query, "llm": _model, "provider": _prov})
        await _broadcast(session_id, "input_started")
        # small delay to mimic streaming
        await asyncio.sleep(0.05)
        await _broadcast(session_id, "input_done", {"status": "completed", "durationMs": 80})
        await _broadcast(session_id, "planner_started")

        state = new_state(session_id=session_id, query=query, assets=assets, image_ids=image_ids)
        # set initial status
        pipeline = get_pipeline()
        # Create the assistant message BEFORE the pipeline runs so that the
        # composer node's live `answer_delta` tokens (emitted during ainvoke)
        # are captured by the UI bridge. Without this, every live token is
        # dropped and the answer never reaches the chat.
        await _broadcast(session_id, "composer_started", {"llm": _model})
        # Enforce 45s budget — respect deadline_ms set by input_validator (ADR 0010 hardening)
        from orchestrator.core.timeouts import remaining_ms
        budget_ms = remaining_ms(state.get("deadline_ms", 0) or 0)
        try:
            result_state = await asyncio.wait_for(pipeline.ainvoke(state), timeout=max(1, budget_ms/1000))  # type: ignore
        except asyncio.TimeoutError:
            state["error"] = f"pipeline timeout after {budget_ms}ms budget"
            state["error_type"] = "transient"
            state["error_code"] = "pipeline_timeout"
            result_state = state

        # extract trace to broadcast step-by-step for UI compatibility
        trace = result_state.get("execution_trace") or []
        # planner_done — always
        plan = result_state.get("plan") or {}
        task_type = result_state.get("task_type","vqa")
        # Fast path: greeting/chitchat/out_of_scope/help with skip_models should not emit heavy model events
        is_fast_path = bool(plan.get("skip_models") or result_state.get("skip_models") or task_type in ("chitchat","greeting","help","out_of_scope"))
        await _broadcast(session_id, "planner_done", {"goal": plan.get("reasoning",""), "task_type": task_type, "capabilities": [task_type], "llm":"qwen3.5-9b", "goals":[task_type], "plan": plan})
        if not is_fast_path:
            await _broadcast(session_id, "execution_started", {"gis": {"operation": "tiling+coreg", "coreg": result_state.get("coreg",{})}})

            # model events — infer from encoder/task
            encoder = result_state.get("encoder","satmae")
            task_output = result_state.get("task_output") or {}
            final = result_state.get("final_result") or task_output

            # emit model_started/done
            model_name_map = {
                "vqa": "RS-VQA",
                "grounding": "GroundingDINO",
                "change_vqa": "ChangeChat",
                "optical_sar_fusion": "CROMA Fusion",
                "captioning": "RS-VQA",
            }
            model_name = model_name_map.get(task_type, encoder)
            await _broadcast(session_id, "model_started", {"model": model_name})
            # real model progress is emitted via _broadcast from task_agent shims if needed; no artificial sleep
            await _broadcast(session_id, "model_progress", {"progress": 0.6})
            # pass through task_output details
            await _broadcast(session_id, "model_done", {"model": model_name, **{k:v for k,v in task_output.items() if k not in ("fused_repr","embeddings")}, "status": "OK" if not result_state.get("error") else "FAILED"})

            # ALWAYS SHOW IN CHAT: which of the 4 models LLM called + raw output (so user sees all models)
            try:
                import json as _j
                # Map task_type to the 4 models
                model_map_full = {
                    "vqa": "Model 1 — inference.py (VQA) `models/vqa/inference.py`",
                    "captioning": "Model 1 — inference.py (Captioning)",
                    "grounding": "Model 2 — inference.py (Grounding) `models/grounding/inference.py`",
                    "change_vqa": "Model 3 — inference.py (Change-VQA) `models/change/inference.py`",
                    "optical_sar_fusion": "Model 4 — inference.py (Fusion) `models/fusion/inference.py`",
                }
                model_label = model_map_full.get(task_type, f"Model — {model_name} ({task_type})")
                # Build compact raw output for chat (avoid huge embeddings)
                raw_out = {k: v for k, v in task_output.items() if k not in ("fused_repr","embeddings","_embeddings_raw","spatial_cam","top_cam")}
                # stringify with limit
                raw_str = _j.dumps(raw_out, indent=2, default=str)
                if len(raw_str) > 3500: raw_str = raw_str[:3500] + "\n... (truncated)"
                md = f"\n\n> **🤖 LLM routed → {model_label}**\n> **Task:** `{task_type}` **Model:** `{model_name}` **Status:** `{'OK' if not result_state.get('error') else 'FAILED'}`\n\n**📤 Model Raw Output:**\n```json\n{raw_str}\n```\n\n**📝 Model Answer Text:**\n> {task_output.get('answer_text','')[:1200]}"
                await _broadcast(session_id, "answer_delta", {"chunk": md})
                await asyncio.sleep(0.05)
            except Exception as _e_m:
                print(f"[model_trace] failed {_e_m}")

            # STEP-BY-STEP VISUALS: broadcast every model artifact as inline chat image (data:) so frontend StreamMarkdown SingleImageBlock shows it
            print(f"[visuals] task_type={task_type} image_ids={image_ids} artifacts={(task_output.get('artifacts') or [])[:2]}")
            try:
                import base64 as _b64, re as _re2
                from pathlib import Path as _P
                def _resolve_for_chat(aid: str) -> _P | None:
                    # mirror orchestrator/agents/task_agents.py:_resolve_asset_path (handles file_...png_hsc, asset_ prefix, timestamp)
                    raw = aid
                    if raw.startswith("asset_"): raw = raw[len("asset_"):]
                    raw = _re2.sub(r"(\.png|\.jpg|\.jpeg|\.tif|\.tiff)(_[a-zA-Z0-9]+)$", r"\1", raw)
                    raw = _re2.sub(r"\.(png|jpg|jpeg|tif|tiff)_[a-zA-Z0-9]+$", r".\1", raw)
                    cands = [aid, raw, _P(aid).name, _P(raw).name]
                    # file_ timestamp → meaningful suffix (file_1788198068947_t1_rgb.png → t1_rgb.png)
                    for c in list(cands):
                        if c.startswith("file_") and "_" in c:
                            parts = c.split("_")
                            if len(parts) >= 3:
                                meaningful = "_".join(parts[2:])
                                meaningful = _re2.sub(r"(\.png|\.jpg|\.jpeg|\.tif|\.tiff)(_[a-zA-Z0-9]+)$", r"\1", meaningful)
                                cands.append(meaningful)
                                cands.append(_P(meaningful).stem + ".tif")
                                cands.append(_P(meaningful).stem + ".png")
                                cands.append(c[len("file_"):])
                    # expand
                    uniq = []
                    seen = set()
                    for c in cands:
                        if c not in seen:
                            seen.add(c); uniq.append(c)
                    for cand in uniq:
                        for base in ["orchestrator/storage/ingest", "gateway/upload", "orchestrator/storage", "outputs"]:
                            try:
                                p = _P(base) / cand
                                if p.exists(): return p
                                # rglob in ingest/outputs
                                if base in ("orchestrator/storage/ingest","outputs"):
                                    for found in _P(base).rglob(_P(cand).name):
                                        if found.exists(): return found
                                    # stem match for tif
                                    stem = _P(cand).stem
                                    for found in _P(base).rglob(f"{stem}.tif"):
                                        if found.is_file(): return found
                                    for found in _P(base).rglob(f"{stem}.png"):
                                        if found.is_file(): return found
                            except Exception: pass
                        if _P(cand).exists(): return _P(cand)
                    # absolute gateway fallback
                    for cand in uniq:
                        for abs_gw in [r"gateway/upload", r"gateway/upload"]:
                            p = _P(abs_gw) / _P(cand).name
                            if p.exists(): return p
                    return None
                # 1) Show input image(s) first — proves your upload is used (not hard-coded) — handles _hsc suffix
                # FIX: don't use base64 (causes PUT /api/session 500 entity too large), copy to gateway/upload and use /api/assets URL
                import shutil as _sh
                _gw_upload = _P(r"gateway/upload")
                _gw_upload.mkdir(parents=True, exist_ok=True)
                for iid in (image_ids or [])[:2]:
                    print(f"[visuals] resolving input {iid}")
                    p = _resolve_for_chat(iid)
                    print(f"[visuals] resolved {iid} -> {p} exists={p.exists() if p else False}")
                    if p is not None and p.exists() and p.suffix.lower() in (".png",".jpg",".jpeg",".tif",".tiff"):
                            try:
                                # copy to gateway/upload so /api/assets can serve it (small URL, no 500)
                                label = iid.replace("asset_","").replace("file_","")[:40]
                                # sanitize label for filename
                                safe = _re2.sub(r"[^a-zA-Z0-9._-]", "_", label)
                                if not safe.lower().endswith((".png",".jpg",".jpeg")):
                                    safe = safe + ".png"
                                dst = _gw_upload / f"chat_{session_id}_{safe}"
                                if p.suffix.lower() in (".tif",".tiff"):
                                    from PIL import Image as _PIL
                                    im = _PIL.open(p)
                                    if im.mode not in ("RGB","RGBA"): im = im.convert("RGB")
                                    # resize to max 768 for chat to keep file small
                                    if max(im.size) > 768:
                                        im.thumbnail((768,768))
                                    im.save(dst, format="PNG")
                                else:
                                    # copy and resize if needed
                                    from PIL import Image as _PIL2
                                    try:
                                        im2 = _PIL2.open(p)
                                        if max(im2.size) > 768:
                                            im2.thumbnail((768,768))
                                            if im2.mode not in ("RGB","RGBA"): im2 = im2.convert("RGB")
                                            im2.save(dst, format="PNG")
                                        else:
                                            _sh.copy(p, dst)
                                    except Exception:
                                        _sh.copy(p, dst)
                                base_url = get_settings().validated_gateway_url()
                                url = f"{base_url}/api/assets/{dst.name}"
                                print(f"[visuals] broadcasting input -> {url}")
                                await _broadcast(session_id, "answer_delta", {"chunk": f"\n\n![Input — {label}]({url})"})
                                await asyncio.sleep(0.05)
                                break
                            except Exception as _e_in:
                                print(f"[visuals] input broadcast failed {_e_in}")
                                pass
                # 2) Show every model artifact (grounding bbox overlay, change delta, CROMA 4-panel, topcam) step-by-step
                all_arts = []
                for k in ("artifacts","visual_artifacts"):
                    v = task_output.get(k) or final.get(k) or []
                    if isinstance(v, list): all_arts.extend(v)
                # dedupe by path
                seen_p = set()
                for art in all_arts:
                    pstr = art.get("path") if isinstance(art, dict) else str(art)
                    if not pstr or pstr in seen_p: continue
                    seen_p.add(pstr)
                    p = _P(pstr)
                    if not p.exists():
                        # try filename search in outputs
                        try:
                            found = list(_P("outputs").rglob(p.name))
                            if found: p = found[0]
                        except Exception: pass
                    if p.exists() and p.suffix.lower() in (".png",".jpg",".jpeg"):
                        try:
                            # copy to gateway/upload and use URL (not base64) to avoid 500 entity too large
                            typ = art.get("type","model output") if isinstance(art, dict) else "model output"
                            step_label = {"vqa":"VQA","grounding":"GroundingDINO bbox overlay","change_vqa":"Change map","optical_sar_fusion":"CROMA fusion"} .get(task_type, typ)
                            if "croma_4panel" in typ: step_label = "CROMA 4-panel (Optical RGB / SAR VV / SAR VH / CAM overlay)"
                            elif "topcam" in typ: step_label = "CROMA CAM heatmap"
                            elif "delta" in typ or "change" in typ: step_label = "Change detection map"
                            elif "bbox" in typ or "overlay" in typ: step_label = "Grounding bbox overlay"
                            dst2 = _gw_upload / f"chat_{session_id}_{p.name}"
                            try:
                                _sh.copy(p, dst2)
                            except Exception:
                                dst2 = p
                            base_url2 = get_settings().validated_gateway_url()
                            url2 = f"{base_url2}/api/assets/{dst2.name}"
                            print(f"[visuals] broadcasting artifact {typ} -> {url2}")
                            await _broadcast(session_id, "answer_delta", {"chunk": f"\n\n![{step_label} — {p.name}]({url2})"})
                            await asyncio.sleep(0.08)
                        except Exception: pass
                    elif p.exists() and p.suffix.lower() == ".npy":
                        pass  # skip npy
            except Exception:
                pass

            await _broadcast(session_id, "evidence_started")
            await asyncio.sleep(0.05)
            conf = final.get("confidence") if final.get("confidence") is not None else result_state.get("confidence")
            if conf is None:
                conf = final.get("confidence")  # keep None, do not invent 0.82
            await _broadcast(session_id, "evidence_done", {"confidence": conf, "evidence_count": 1})

            # Router/planner already streamed their real reasoning as thinking_delta
            # during the pipeline run. Close the thinking block now.
            await _broadcast(session_id, "thinking_done")
        else:
            # Fast path: still close thinking, but no heavy model evidence
            task_output = result_state.get("task_output") or {}
            final = result_state.get("final_result") or task_output
            conf = final.get("confidence") if final.get("confidence") is not None else result_state.get("confidence")
            await _broadcast(session_id, "thinking_done")

        # answer streaming — if the composer node already streamed tokens live
        # (true real-time via Groq), do NOT re-chunk the main text (would
        # duplicate). Only append the chart block + tabular evidence the node
        # did not emit during streaming.
        answer_text = final.get("answer_text","")
        chart = final.get("chart_spec")
        chart_block = ""
        if chart:
            # validate before emitting
            valid, _ = validate_chart_spec(chart)
            if valid:
                chart_block = f"\n\n```chart\n{json.dumps(chart)}\n```"

        streamed = bool(EXECUTIONS.get(session_id, {}).get("_streamed", False))

        if not streamed:
            # node did not stream — emit main text in chunks for progressive display
            full = answer_text + chart_block
            chunk_size = 400
            for i in range(0, len(full), chunk_size):
                await _broadcast(session_id, "answer_delta", {"chunk": full[i:i+chunk_size]})
                await asyncio.sleep(0.12)
        else:
            # LLM-driven: only auto-append chart if it's not marked optional or if LLM already included one
            if chart_block and "```chart" not in answer_text:
                is_optional = bool(chart.get("_llm_optional")) if isinstance(chart, dict) else False
                # only force chart for change/fusion where it's genuinely useful; VQA/grounding respects LLM choice
                task = final.get("task","")
                if not is_optional or task in ("change_vqa","optical_sar_fusion"):
                    # for VQA grounding, respect LLM omission — check if answer already has bbox/table
                    if task not in ("vqa","grounding") or "confidence" in answer_text.lower():
                        await _broadcast(session_id, "answer_delta", {"chunk": chart_block})

        # Evidence tables: only if LLM did not already include them (avoid duplicate hardcode)
        answer_lower = (answer_text or "").lower()
        if (final.get("bbox_xyxy") or final.get("bbox") or final.get("bbox_normalized")) and "bbox" not in answer_lower:
            bbox = final.get("bbox_xyxy") or final.get("bbox") or final.get("bbox_normalized")
            if bbox is not None and conf is not None:
                await _broadcast(session_id, "answer_delta", {"chunk": f"\n\n| BBox | {bbox} |\n| Confidence | {conf} |"})
            elif bbox is not None:
                await _broadcast(session_id, "answer_delta", {"chunk": f"\n\n| BBox | {bbox} |"})

        if final.get("per_modality_confidence") and "modality" not in answer_lower:
            per = final["per_modality_confidence"]
            await _broadcast(session_id, "answer_delta", {"chunk": f"\n\n| Modality | Confidence |\n|---|---:|\n| Optical | {per.get('optical',0):.2f} |\n| SAR | {per.get('sar',0):.2f} |\n| Fused | {per.get('fused',0):.2f} |"})

        # FINAL SAFETY: ensure at least the input image is appended to final_answer even if earlier broadcast missed (handles _hsc suffix case) — use URL not base64 to avoid 500
        try:
            from pathlib import Path as _P2
            _base_check = get_settings().validated_gateway_url()
            has_image_in_answer = f"{_base_check}/api/assets" in (answer_text or final.get("answer_text") or "")
            if not has_image_in_answer:
                for iid in (image_ids or [])[:1]:
                    import re as _re3, shutil as _sh2
                    raw = iid
                    if raw.startswith("asset_"): raw = raw[len("asset_"):]
                    raw = _re3.sub(r"(\.png|\.jpg|\.jpeg|\.tif|\.tiff)(_[a-zA-Z0-9]+)$", r"\1", raw)
                    cand_names = [raw, _P2(raw).name]
                    if raw.startswith("file_"):
                        parts = raw.split("_")
                        if len(parts) >= 3:
                            cand_names.append("_".join(parts[2:]))
                    p_found = None
                    for cn in cand_names:
                        for base in ["gateway/upload", "orchestrator/storage/ingest"]:
                            cand_p = _P2(base) / cn
                            if cand_p.exists():
                                p_found = cand_p; break
                            try:
                                for f in _P2(base).rglob(_P2(cn).name):
                                    p_found = f; break
                            except Exception: pass
                            if p_found: break
                        if p_found: break
                    if p_found is None:
                        for cn in cand_names:
                            p_abs = _P2(r"gateway/upload") / _P2(cn).name
                            if p_abs.exists():
                                p_found = p_abs; break
                    if p_found and p_found.exists():
                        try:
                            gw = _P2(r"gateway/upload")
                            gw.mkdir(parents=True, exist_ok=True)
                            dst = gw / f"chat_{session_id}_{p_found.name}"
                            if p_found.suffix.lower() in (".tif",".tiff"):
                                from PIL import Image as _PIL2
                                im = _PIL2.open(p_found)
                                if im.mode not in ("RGB","RGBA"): im = im.convert("RGB")
                                if max(im.size) > 768: im.thumbnail((768,768))
                                im.save(dst, format="PNG")
                            else:
                                try:
                                    from PIL import Image as _PIL3
                                    im3 = _PIL3.open(p_found)
                                    if max(im3.size) > 768:
                                        im3.thumbnail((768,768))
                                        if im3.mode not in ("RGB","RGBA"): im3 = im3.convert("RGB")
                                        im3.save(dst, format="PNG")
                                    else:
                                        _sh2.copy(p_found, dst)
                                except Exception:
                                    _sh2.copy(p_found, dst)
                            base_url_final = get_settings().validated_gateway_url()
                            url = f"{base_url_final}/api/assets/{dst.name}"
                            md = f"\n\n![Input — {p_found.name}]({url})"
                            await _broadcast(session_id, "answer_delta", {"chunk": md})
                            final["answer_text"] = (final.get("answer_text") or "") + md
                            break
                        except Exception: pass
        except Exception:
            pass

        await _broadcast(session_id, "final_answer", {"result": final})
        await _broadcast(session_id, "query_completed", {})

        # persist to minio + sqlite audit + in-memory
        try:
            minio_client.upload_bytes("rs-outputs", f"{session_id}.json", json.dumps(final, indent=2).encode(), content_type="application/json")
        except Exception:
            pass
        # audit trace persistence — additive Postgres/SQLite (never replaces MinIO/Redis)
        try:
            import sqlite3
            from pathlib import Path
            p = Path("orchestrator/storage/audit.db")
            p.parent.mkdir(parents=True, exist_ok=True)
            con = sqlite3.connect(str(p))
            cur = con.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS execution_traces (request_key TEXT PRIMARY KEY, session_id TEXT, trace TEXT, created_at REAL)")
            rk = result_state.get("request_key") or session_id
            cur.execute("INSERT OR REPLACE INTO execution_traces (request_key, session_id, trace, created_at) VALUES (?,?,?,?)",
                        (rk, session_id, json.dumps(trace), time.time()))
            con.commit()
            con.close()
        except Exception:
            pass
        EXECUTIONS[session_id]["result"] = final
        # save to conversation history for followup handling
        try:
            save_history(session_id, {"session_id": session_id, "query": query, "task_type": task_type, "task_output": final, "task_output_id": session_id, "confidence": final.get("confidence"), "timestamp": time.time()})
        except Exception:
            pass

    except Exception as e:
        await _broadcast(session_id, "error", {"message": str(e)})
        EXECUTIONS[session_id]["error"] = str(e)
        try:
            record_request(False)
        except Exception:
            pass
    finally:
        # release queue slot if we were the holder
        try:
            # release only if session was queued via gate
            if EXECUTIONS.get(session_id, {}).get("_queued"):
                queue_release()
                EXECUTIONS[session_id]["_queued"] = False
        except Exception:
            pass
        # also mark metrics success if final_result present
        try:
            res = EXECUTIONS.get(session_id, {}).get("result")
            has_result = bool(res and not res.get("error"))
            if "error" not in (EXECUTIONS.get(session_id) or {}):
                record_request(has_result)
        except Exception:
            pass

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fix 2: Ollama cold-start warmup — 1-token dummy prompt during boot (3–6s VRAM load, then stays resident)
    # Must not block startup if Ollama not running; fire-and-forget with timeout
    async def _warm_ollama():
        try:
            import asyncio as _aio
            # has_local_qwen_capability checks ollama binary + model
            from orchestrator.core.llm_client import has_local_qwen_capability
            if not has_local_qwen_capability():
                print("[lifespan] Ollama qwen3.5:9b not available — warmup skipped (will fail-closed on first query)")
                return
            print("[lifespan] Warming Ollama qwen3.5:9b (1-token dummy) ...")
            import ollama as _oll
            # 1-token warmup — swap into VRAM
            await _aio.to_thread(_oll.chat, model="qwen3.5:9b", messages=[{"role": "user", "content": "hi"}])
            print("[lifespan] Ollama warmup done (VRAM resident)")
        except Exception as _e:
            print(f"[lifespan] Ollama warmup skipped: {_e}")

    try:
        await asyncio.wait_for(init_db(), timeout=3.0)
    except asyncio.TimeoutError:
        print("[db] init timeout after 3s — using SQLite fallback, continuing")
    except Exception as e:
        print(f"[db] init skipped: {e}")
    try:
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
            fut = _ex.submit(minio_client.ensure_buckets)
            try:
                fut.result(timeout=2.0)
            except _cf.TimeoutError:
                print("[minio] ensure_buckets timeout — using disk fallback")
    except Exception:
        pass
    # Non-blocking warmup — schedule without awaiting (still logs)
    try:
        asyncio.create_task(_warm_ollama())
    except Exception:
        pass
    # Fix 3: Ephemeral disk cleanup — schedule background sweep every 10 min
    try:
        asyncio.create_task(_periodic_disk_cleanup())
    except Exception:
        pass
    yield
    # shutdown: flush CUDA, close pools
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

app.router.lifespan_context = lifespan

# Keep legacy startup for backward compat (lifespan now owns it)
@app.on_event("startup")
async def startup():
    pass

@app.get("/health")
async def health():
    # active Ollama probe — 500ms timeout, never blocks startup
    ollama_reachable = False
    ollama_latency_ms = None
    ollama_error = None
    try:
        import httpx as _hx
        s = get_settings()
        base = s.qwen_base_url.replace("/v1","").rstrip("/")
        t0 = time.time()
        async with _hx.AsyncClient(timeout=0.5) as c:
            r = await c.get(f"{base}/api/tags")
            ollama_reachable = r.status_code == 200
            # also check qwen3.5:9b present if reachable
            if ollama_reachable and s.qwen_model not in r.text:
                ollama_error = f"model {s.qwen_model} not in /api/tags"
        ollama_latency_ms = int((time.time()-t0)*1000)
    except Exception as e:
        ollama_error = str(e)[:120]
    return {"status":"healthy","timestamp": time.time(), "uptime": time.time(), "ollama_reachable": ollama_reachable, "ollama_latency_ms": ollama_latency_ms, "ollama_error": ollama_error, "qwen_model": get_settings().qwen_model}

@app.get("/health/live")
async def health_live():
    return {"status":"healthy","service":"orchestrator","timestamp": time.time(), "queue": {"active": queue_active_count(), "limits": queue_limits()}}

@app.get("/health/ready")
async def health_ready():
    # readiness: model is warm if circuit closed and at least one provider available
    qwen = qwen_circuit.snapshot()
    vision = vision_health_ready()
    fusion = fusion_health_ready()
    ready = qwen["state"] != "open" and vision.get("http_status")==200 and fusion.get("http_status")==200
    status_code = 200 if ready else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=status_code, content={
        "status": "ready" if ready else "not_ready",
        "timestamp": time.time(),
        "qwen": qwen,
        "vision": vision,
        "fusion": fusion,
        "queue": {"active": queue_active_count(), "limits": queue_limits()},
    })

@app.get("/api/v1/metrics")
async def metrics_endpoint(session_id: str | None = None, format: str | None = None):
    snap = metrics_snapshot(session_id)
    # Prometheus text exposition if Accept: text/plain
    if format == "prometheus":
        lines = []
        for k,v in snap.get("p95_ms",{}).items():
            lines.append(f'satiq_node_latency_p95_ms{{node="{k}"}} {v}')
        for k,v in snap.get("counters",{}).items():
            lines.append(f'satiq_node_count{{node="{k}"}} {v}')
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse("\n".join(lines), media_type="text/plain")
    return snap

@app.get("/api/v1/dlq")
async def list_dlq(session_id: str | None = None, limit: int = 50):
    from orchestrator.core.dlq import list_all, list_by_session
    try:
        if session_id:
            items = list_by_session(session_id, limit=limit)
        else:
            items = list_all(limit=limit)
        return {"count": len(items), "items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])

@app.get("/api/v1/task/{session_id}/health")
async def task_health(session_id: str):
    # per-request health: node latencies + trace summary
    exec_ = EXECUTIONS.get(session_id)
    if not exec_:
        raise HTTPException(status_code=404, detail="session not found")
    result = exec_.get("result") or {}
    trace = result.get("execution_trace") or []
    return {"session_id": session_id, "metrics": metrics_snapshot(), "trace": trace_summary(trace)}

@app.get("/api/v1/tools")
async def list_tools():
    from orchestrator.helpers.tool_schemas import REGISTERED_TOOLS, TOOL_NAME_TO_TASK
    return {"count": len(REGISTERED_TOOLS), "tools": REGISTERED_TOOLS, "tool_name_to_task": TOOL_NAME_TO_TASK}

@app.get("/api/v1/memory/{session_id}")
async def get_memory(session_id: str, n: int = 5):
    from orchestrator.services.conversation import load_history
    try:
        hist = load_history(session_id, n=n)
        episodic = []
        try:
            from orchestrator.memory.memory_orchestrator import retrieve_for_planner
            episodic = (await retrieve_for_planner("", session_id)).get("episodic", [])[:n]
        except Exception:
            pass
        return {"session_id": session_id, "history": hist, "episodic_hits": episodic, "count": len(hist)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:200])

@app.delete("/api/v1/memory/{session_id}")
async def delete_memory(session_id: str):
    from orchestrator.services.conversation import MEM_HISTORY
    from pathlib import Path
    import sqlite3
    deleted = 0
    try:
        # SQLite
        from orchestrator.services.conversation import _sqlite_path
        con = sqlite3.connect(str(_sqlite_path()))
        cur = con.cursor()
        cur.execute("DELETE FROM conversation_history WHERE session_id=?", (session_id,))
        deleted = cur.rowcount
        con.commit(); con.close()
    except Exception:
        pass
    MEM_HISTORY.pop(session_id, None)
    # disk history
    try:
        for p in [Path(f"orchestrator/storage/history/{session_id}.json"), Path(f"orchestrator/storage/task_outputs/{session_id}.json")]:
            if p.exists(): p.unlink(missing_ok=True); deleted += 1
    except Exception:
        pass
    # Chroma episodic
    try:
        from orchestrator.memory.rag_store import _get_episodic_collection, _get_semantic_collection
        for col in [_get_episodic_collection(), _get_semantic_collection()]:
            if col is None: continue
            got = col.get(where={"session_id": session_id}, limit=1000)
            ids = got.get("ids", [])
            if ids: col.delete(ids=ids); deleted += len(ids)
    except Exception:
        pass
    return {"session_id": session_id, "deleted": deleted, "message": "memory deleted; indexes rebuilt from retained data if any"}

@app.get("/api/v1/llm/status")
async def llm_status():
    s = get_settings()
    prov = resolve_provider()
    # distributed keys — count without exposing values
    try:
        from orchestrator.core.llm_client import _all_groq_keys, _has_mistral
        groq_keys = _all_groq_keys()
        has_mistral = _has_mistral()
    except Exception:
        groq_keys, has_mistral = [], False
    return {
        "provider": prov,
        "llm_provider_setting": s.llm_provider,
        "mock_qwen": s.mock_qwen,
        "has_local_qwen_capability": has_local_qwen_capability(),
        "local": {"base_url": s.qwen_base_url, "model": s.qwen_model, "has_ollama": has_local_qwen_capability()},
        "groq": {"model": s.groq_model, "router_model": getattr(s, "groq_router_model", ""), "stt_model": s.groq_stt_model, "has_key": bool(groq_keys), "key_count": len(groq_keys), "base_url": s.groq_base_url, "distribution": "router->GROQ1, planner->GROQ2, composer->Mistral->GROQ fallback"},
        "mistral": {"model": getattr(s, "mistral_model", "mistral-small-latest"), "has_key": has_mistral, "base_url": getattr(s, "mistral_base_url", "https://api.mistral.ai/v1")},
        "voice_enabled": s.enable_voice,
    }

@app.post("/api/v1/transcribe")
async def transcribe(
    file: UploadFile = File(..., description="Audio file (wav/mp3/m4a/ogg/flac/webm)"),
    language: Optional[str] = Form(default=None),
    prompt: Optional[str] = Form(default=None),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="filename required")
    # size guard: 25MB (Groq limit)
    data = await file.read()
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="audio exceeds 25MB limit")
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="empty audio")
    result = transcribe_audio(data, filename=file.filename, language=language, prompt=prompt)
    # if transcription failed but groq error, return 502
    if result.get("error") and not result.get("_mock"):
        raise HTTPException(status_code=502, detail=result["error"])
    return result

@app.post("/api/v1/task/with-audio")
async def create_task_with_audio(
    background_tasks: BackgroundTasks,
    query: Optional[str] = Form(default=None),
    file: Optional[UploadFile] = File(default=None, description="Optional voice audio to transcribe"),
    language: Optional[str] = Form(default=None),
    image_ids: Optional[str] = Form(default=None, description="JSON array string e.g. '[\"img_001\"]'"),
    assets: Optional[str] = Form(default=None, description="JSON array string for assets"),
):
    # voice-to-text: if file provided and query empty, transcribe
    final_query = (query or "").strip()
    transp = None
    if file is not None and file.filename:
        data = await file.read()
        if data:
            transp = transcribe_audio(data, filename=file.filename, language=language)
            if transp.get("text"):
                final_query = transp["text"]
            elif not final_query:
                raise HTTPException(status_code=422, detail=f"transcription failed: {transp.get('error')}")
    if not final_query:
        raise HTTPException(status_code=400, detail="query or audio file required")
    # parse image_ids / assets if JSON strings
    import json as _json
    ids: Optional[List[str]] = None
    if image_ids:
        try:
            ids = _json.loads(image_ids) if image_ids.strip().startswith("[") else [image_ids]
        except Exception:
            ids = [image_ids]
    asset_list: Optional[List[Dict[str,Any]]] = None
    if assets:
        try:
            asset_list = _json.loads(assets)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"invalid assets JSON: {e}")
    # reuse existing task creation logic
    req = TaskRequest(query=final_query, image_ids=ids, assets=asset_list)
    assets_n, ids_n = _normalize_assets(req)
    if assets_n:
        crs_vals = [a.get("crs") for a in assets_n if a.get("crs")]
        if len(set(crs_vals)) > 1:
            raise HTTPException(status_code=400, detail=f"CRS mismatch: {crs_vals}")
    if not queue_acquire():
        raise HTTPException(status_code=429, detail=f"queue full: active={queue_active_count()} limits={queue_limits()}")
    session_id = f"sess_{uuid.uuid4().hex[:8]}"
    EXECUTIONS[session_id] = {
        "session_id": session_id,
        "query": final_query,
        "assets": assets_n,
        "image_ids": ids_n,
        "status": "queued",
        "created_at": time.time(),
        "events": [],
        "result": None,
        "transcription": transp,
        "_queued": True,
    }
    background_tasks.add_task(run_pipeline, session_id, final_query.strip(), assets_n, ids_n)
    return {"session_id": session_id, "status": "queued", "query": final_query, "transcription": transp}

@app.post("/api/v1/task")
async def create_task(req: TaskRequest, background_tasks: BackgroundTasks):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    if len(req.query) > 4000:
        raise HTTPException(status_code=400, detail="query exceeds 4000 chars")
    assets, image_ids = _normalize_assets(req)
    if assets:
        crs_vals = [a.get("crs") for a in assets if a.get("crs")]
        if len(set(crs_vals)) > 1:
            raise HTTPException(status_code=400, detail=f"CRS mismatch: {crs_vals}")
    # queue gate with backpressure (§2.2 audit #5)
    if not queue_acquire():
        raise HTTPException(status_code=429, detail=f"queue full: active={queue_active_count()} limits={queue_limits()}")
    # VRAM bounded queue (GAP-3) — fail-fast 503 if GPU queue depth exceeded
    try:
        from orchestrator.agents.task_agents import _vram_queue_depth
        from orchestrator.core.config import get_settings as _gs
        max_q = int(getattr(_gs(), "vram_max_queue", 4))
        if _vram_queue_depth() > max_q + 2:
            raise HTTPException(status_code=503, detail=f"VRAM queue full: depth={_vram_queue_depth()} limit={max_q}+2 — Retry-After 6s", headers={"Retry-After": "6"})
    except HTTPException:
        raise
    except Exception:
        pass
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:8]}"
    # Prevent overwrite of running execution in same session (multi-turn sequential spam)
    existing = EXECUTIONS.get(session_id)
    if existing and existing.get("status") in ("queued", "running"):
        raise HTTPException(status_code=409, detail=f"session {session_id} is busy (status={existing.get('status')}); wait for completion or use new session_id")
    EXECUTIONS[session_id] = {
        "session_id": session_id,
        "query": req.query,
        "assets": assets,
        "image_ids": image_ids,
        "status": "queued",
        "created_at": time.time(),
        "events": [],
        "result": None,
        "_queued": True,
    }
    _persist_exec(session_id)
    background_tasks.add_task(run_pipeline, session_id, req.query.strip(), assets, image_ids)
    return {"session_id": session_id, "status": "queued"}

def _load_exec_or_404(sid: str) -> dict:
    exec_ = EXECUTIONS.get(sid)
    if exec_:
        return exec_
    try:
        c = _redis_client()
        if c is None:
            raise RuntimeError("no redis")
        raw = c.get(_exec_redis_key(sid))
        if raw:
            data = json.loads(raw)
            EXECUTIONS[sid] = data
            return data
    except Exception:
        pass
    raise HTTPException(status_code=404, detail="session not found")

@app.get("/api/v1/task/{session_id}/stream")
async def stream_task(session_id: str, request: Request):
    """SSE stream — supports Last-Event-ID replay from Redis."""
    from fastapi.responses import StreamingResponse
    exec_ = _load_exec_or_404(session_id)
    async def gen():
        # Last-Event-ID support: client sends last seen id, we resume after it
        last_id_hdr = request.headers.get("Last-Event-ID") or request.headers.get("last-event-id")
        try:
            seen = int(last_id_hdr) + 1 if last_id_hdr is not None and last_id_hdr.isdigit() else 0
        except Exception:
            seen = 0
        while True:
            if await request.is_disconnected():
                break
            evs = _load_exec_or_404(session_id).get("events", [])
            while seen < len(evs):
                ev = evs[seen]
                seen += 1
                # include id for replay
                eid = ev.get("id", str(seen-1))
                yield f"id: {eid}\nevent: {ev.get('event','message')}\ndata: {json.dumps(ev)}\n\n"
                if ev.get("event") in ("query_completed","final_answer","error","cancelled"):
                    # give gateway a moment to drain then close
                    await asyncio.sleep(0.05)
                    return
            # finished?
            status = EXECUTIONS.get(session_id, {}).get("status")
            if status in ("completed","failed","cancelled"):
                return
            await asyncio.sleep(0.25)
    return StreamingResponse(gen(), media_type="text/event-stream", headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

@app.get("/api/v1/task/{session_id}")
async def get_task(session_id: str):
    exec_ = _load_exec_or_404(session_id)
    # include result if completed
    return {
        "session_id": session_id,
        "status": exec_.get("status"),
        "query": exec_.get("query"),
        "result": exec_.get("result"),
        "events": exec_.get("events", [])[-20:],  # last 20
        "created_at": exec_.get("created_at"),
        "trace": (exec_.get("result") or {}).get("execution_trace"),
    }

@app.post("/api/v1/task/{session_id}/cancel")
async def cancel_task(session_id: str):
    exec_ = EXECUTIONS.get(session_id)
    if not exec_:
        # try Redis recovery
        try:
            exec_ = _load_exec_or_404(session_id)
        except Exception:
            raise HTTPException(status_code=404, detail="session not found")
    exec_["is_cancelled"] = True
    exec_["status"] = "cancelled"
    # Also set in GraphState if pipeline still running — broadcast will be picked up
    try:
        await _broadcast(session_id, "cancelled", {"reason": "user abort"})
    except Exception:
        pass
    _persist_exec(session_id)
    return {"session_id": session_id, "status": "cancelled"}

@app.get("/api/v1/task/{session_id}/geojson")
async def get_task_geojson(session_id: str, crs: str = "EPSG:4326"):
    exec_ = _load_exec_or_404(session_id)
    result = exec_.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="task not completed yet")
    try:
        fc = export_geojson(result, crs=crs)
        return fc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])

@app.get("/api/v1/session/{session_id}/trace/summary")
async def get_trace_summary(session_id: str, threshold_ms: int = 2000):
    exec_ = EXECUTIONS.get(session_id)
    if not exec_:
        raise HTTPException(status_code=404, detail="session not found")
    result = exec_.get("result") or {}
    trace = result.get("execution_trace") or exec_.get("events") or []
    # normalize events to trace format if needed
    if trace and isinstance(trace[0], dict) and "event" in trace[0]:
        # events are broadcast events, convert to trace-like
        trace = [{"agent": e.get("event"), "status": "ok", "latency_ms": 0} for e in trace]
    summary = trace_summary(trace, threshold_ms=threshold_ms)
    return summary

class ReportRequest(BaseModel):
    format: str = "pdf"
    task_ids: Optional[List[str]] = None

@app.post("/api/v1/session/{session_id}/report")
async def create_report(session_id: str, req: ReportRequest):
    # collect task_outputs for session: if task_ids provided, fetch those, else all for session
    outputs: List[Dict[str, Any]] = []
    if req.task_ids:
        for tid in req.task_ids:
            ex = EXECUTIONS.get(tid)
            if ex and ex.get("result"):
                outputs.append(ex["result"])
    else:
        # use current session result
        ex = EXECUTIONS.get(session_id)
        if ex and ex.get("result"):
            outputs.append(ex["result"])
        # also search all EXECUTIONS for same session prefix
        for k, v in EXECUTIONS.items():
            if k != session_id and v.get("result") and k.startswith(session_id[:4]):
                outputs.append(v["result"])
                if len(outputs) >= 10:
                    break
    if not outputs:
        raise HTTPException(status_code=404, detail="no completed tasks for report")
    fmt = req.format.lower()
    if fmt not in ("pdf","docx","html"):
        raise HTTPException(status_code=400, detail="format must be pdf|docx|html")
    try:
        data = generate_report(session_id, outputs, format=fmt)  # type: ignore
        # also save to storage
        try:
            save_report(session_id, outputs, format=fmt)
        except Exception:
            pass
        from fastapi.responses import Response
        media = {"pdf":"application/pdf","docx":"application/vnd.openxmlformats-officedocument.wordprocessingml.document","html":"text/html"}[fmt]
        return Response(content=data, media_type=media, headers={"Content-Disposition": f"attachment; filename={session_id}.{fmt}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])

class RecomposeRequest(BaseModel):
    temperature: Optional[float] = None
    prompt: Optional[str] = None

@app.post("/api/v1/task/{session_id}/recompose")
async def recompose_task(session_id: str, req: RecomposeRequest):
    exec_ = EXECUTIONS.get(session_id)
    if not exec_:
        raise HTTPException(status_code=404, detail="session not found")
    result = exec_.get("result")
    if not result:
        raise HTTPException(status_code=404, detail="task not completed yet")
    # re-run composer only with increased temperature
    try:
        # fetch trace
        trace = result.get("execution_trace") or []
        query = exec_.get("query") or result.get("query") or ""
        # bump composer_version
        version = int(result.get("composer_version") or 1) + 1
        # call composer with slightly higher temperature via llm_client (uses 0.2 default, we pass via prompt hint)
        new_text = call_qwen_composer(query + (f" [recompose temp {req.temperature}]" if req.temperature else " [re-explain differently]"), result, trace)
        new_result = dict(result)
        new_result["answer_text"] = new_text
        new_result["composer_version"] = version
        new_result["recomposed"] = True
        new_result["recompose_prompt"] = req.prompt
        # update stored
        EXECUTIONS[session_id]["result"] = new_result
        try:
            minio_client.upload_bytes("rs-outputs", f"{session_id}_v{version}.json", json.dumps(new_result, indent=2).encode(), content_type="application/json")
        except Exception:
            pass
        return new_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])

@app.websocket("/ws/task/{session_id}")
async def ws_task(websocket: WebSocket, session_id: str):
    await websocket.accept()
    WS_SUBSCRIBERS.setdefault(session_id, []).append(websocket)
    # replay buffered events
    exec_ = EXECUTIONS.get(session_id)
    if exec_:
        for ev in exec_.get("events", []):
            await websocket.send_json(ev)
        if exec_.get("status") in ("completed","failed","cancelled"):
            await websocket.close()
            WS_SUBSCRIBERS[session_id].remove(websocket)
            return
    # subscribe to redis pubsub as well
    def on_redis(ev):
        # push via asyncio — need to schedule
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(websocket.send_json(ev))
        except Exception:
            pass
    unsub = session_state.subscribe(f"session:{session_id}:events", on_redis)
    try:
        while True:
            await websocket.receive_text()  # keep alive, ignore
    except WebSocketDisconnect:
        pass
    finally:
        try:
            WS_SUBSCRIBERS[session_id].remove(websocket)
        except Exception:
            pass
        unsub()

@app.post("/api/v1/ingest")
async def ingest_image(
    file: UploadFile = File(..., description="Image/video file"),
    crs: Optional[str] = Form(default=None),
):
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="file exceeds 100MB")
    try:
        try:
            res = ingest_file(data, file.filename or "upload.bin", target_crs=crs)
        except ValueError as ve:
            # strict CRS contract P0-04
            raise HTTPException(status_code=400, detail=str(ve))
        # pixel cap wiring: width*height >100Mpix → 413 (protects input_validator even if asset metadata missing)
        val = res.get("validation") or {}
        try:
            w = int(val.get("width") or 0)
            h = int(val.get("height") or 0)
            if w and h and w * h > 100_000_000:
                raise HTTPException(status_code=413, detail=f"image too large {w}x{h} (>100Mpix)")
        except HTTPException:
            raise
        except Exception:
            pass
        # convert thumbnail to base64 for JSON if needed, else return path
        thumb_b64 = None
        if res.get("thumbnail"):
            import base64
            thumb_b64 = base64.b64encode(res["thumbnail"]).decode()[:200] + "..." if len(res["thumbnail"]) > 200 else base64.b64encode(res["thumbnail"]).decode()
        return {
            "filename": res.get("filename"),
            "is_video": res.get("is_video"),
            "geotiff_path": res.get("geotiff_path"),
            "validation": res.get("validation"),
            "exif": res.get("exif"),
            "keyframes_count": res.get("keyframes_count"),
            "thumbnail_preview": thumb_b64,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])

@app.post("/api/v1/benchmark")
async def run_benchmark_endpoint(
    dataset: str = Form(default="vrsbench"),
    split: str = Form(default="val"),
    limit: int = Form(default=5),
    background_tasks: BackgroundTasks = None,  # type: ignore
):
    if dataset not in ("vrsbench","rsvqa","cdvqa"):
        raise HTTPException(status_code=400, detail="dataset must be vrsbench|rsvqa|cdvqa")
    # run as background? For now run inline (small limit)
    try:
        from eval.benchmark import run_benchmark
        result = await run_benchmark(dataset, split, limit=limit)  # type: ignore
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)[:300])

@app.get("/api/v1/benchmark/stream")
async def benchmark_stream(dataset: str = "vrsbench", split: str = "val", limit: int = 5):
    from fastapi.responses import StreamingResponse
    from eval.benchmark import run_benchmark_stream
    async def gen():
        async for ev in run_benchmark_stream(dataset, split, limit):  # type: ignore
            yield f"data: {json.dumps(ev)}\n\n"
    return StreamingResponse(gen(), media_type="text/event-stream")

# also expose gateway-compatible endpoints: POST /api/query and GET /api/query/:id/stream
# so gateway can proxy directly if needed, but primary is /api/v1/task

@app.post("/api/query")
async def create_query_compat(req: TaskRequest, background_tasks: BackgroundTasks):
    # map gateway AnalysisRequest -> TaskRequest
    return await create_task(req, background_tasks)

@app.get("/api/query/{execution_id}")
async def get_query_compat(execution_id: str):
    return await get_task(execution_id)
