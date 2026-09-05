"""Ollama qwen3.5:9b only — no Groq/Mistral, no mocks, fail-closed."""
from __future__ import annotations
import json
import os
import asyncio
import shutil
import subprocess
import time
from typing import Dict, Any, Optional, Literal

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

try:
    from openai import AsyncOpenAI  # type: ignore
except Exception:
    AsyncOpenAI = None  # type: ignore

from .config import get_settings
try:
    from orchestrator.core.circuit_breaker import qwen_circuit  # type: ignore
except Exception:
    qwen_circuit = None  # type: ignore
try:
    from orchestrator.core.metrics import record_node_latency  # type: ignore
except Exception:
    record_node_latency = None  # type: ignore

# ---------- capability check ----------

def _ollama_binary() -> Optional[str]:
    return shutil.which("ollama")

def _ollama_has_model(model: str) -> bool:
    bin_path = _ollama_binary()
    if not bin_path:
        return False
    try:
        out = subprocess.run([bin_path, "list"], capture_output=True, text=True, timeout=4)
        txt = (out.stdout or "") + (out.stderr or "")
        base = model.split(":")[0].split("/")[-1].lower()
        return base in txt.lower() or model.lower() in txt.lower()
    except Exception:
        return False

def _system_can_run_qwen() -> bool:
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        if vm.available < 3.5 * 1024**3:
            return False
        return True
    except Exception:
        return True

def has_local_qwen_capability() -> bool:
    s = get_settings()
    if not _ollama_binary():
        return False
    if not _system_can_run_qwen():
        return False
    if _ollama_has_model(s.qwen_model):
        return True
    if OpenAI is None:
        return False
    try:
        cli = OpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=3)  # type: ignore
        cli.models.list()  # type: ignore
        return True
    except Exception:
        return False

# ---------- provider ----------

Provider = Literal["local"]

def is_mock_mode() -> bool:
    return False

def _has_any_groq_key() -> bool:
    return False

def resolve_provider() -> Provider:
    s = get_settings()
    prov = (getattr(s, "llm_provider", "auto") or "auto").lower()
    if prov == "mock":
        raise RuntimeError("MOCK forbidden — set LLM_PROVIDER=local and ensure ollama qwen3.5:9b is running")
    if prov == "groq":
        raise RuntimeError("Groq forbidden — use Ollama qwen3.5:9b only (LLM_PROVIDER=local)")
    if not has_local_qwen_capability():
        raise RuntimeError("Ollama qwen3.5:9b not available — ensure ollama serve and `ollama pull qwen3.5:9b`")
    return "local"

def get_sync_client():
    prov = resolve_provider()
    s = get_settings()
    if OpenAI is None:
        raise RuntimeError("OpenAI compat not installed but required for Ollama")
    cli = OpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=12)  # type: ignore
    return cli, "local"

def get_async_client():
    prov = resolve_provider()
    s = get_settings()
    if AsyncOpenAI is None:
        raise RuntimeError("AsyncOpenAI required for Ollama streaming")
    cli = AsyncOpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=12)  # type: ignore
    return cli, "local"

def get_sync_client_for_role(role: str):
    prov = resolve_provider()
    s = get_settings()
    if OpenAI is None:
        raise RuntimeError("OpenAI package required for Ollama OpenAI-compat")
    cli = OpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=12)  # type: ignore
    return cli, "local", s.qwen_model

def get_async_client_for_role(role: str):
    prov = resolve_provider()
    s = get_settings()
    if AsyncOpenAI is None:
        raise RuntimeError("AsyncOpenAI required for Ollama streaming")
    cli = AsyncOpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=12)  # type: ignore
    return cli, "local", s.qwen_model

def _is_connection_error(e: Exception) -> bool:
    msg = str(e).lower()
    return any(k in msg for k in ["connection", "connect", "timeout", "timed out", "no internet", "network", "unreachable", "failed to", "name not resolved", "getaddrinfo", "offline"])

# ---------- helpers ----------

def _strip_think(text: str) -> str:
    import re as _re
    if "</think>" in text:
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    return text.strip()

def _extract_json(text: str) -> str | None:
    import re as _re
    import json as _json
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    candidates = _re.findall(r"\{[^{}]*\"task_type\"[^{}]*\}", text, flags=_re.DOTALL)
    if candidates:
        for cand in reversed(candidates):
            try:
                _json.loads(cand)
                return cand
            except Exception:
                continue
        return candidates[-1]
    idx = text.rfind('"task_type"')
    if idx != -1:
        start = text.rfind("{", 0, idx)
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        if start != -1 and end != -1:
            return text[start:end]
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        return text[start:end]
    return None

def _call_with_timeout(fn, timeout_s: float = 4.0):
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_s)
        except _cf.TimeoutError:
            raise TimeoutError(f"LLM call timed out after {timeout_s}s")

def _call_ollama(prompt: str, tools: list | None = None, json_mode: bool = False) -> tuple[str, list]:
    """Unified Ollama call — returns (raw_content, tool_calls)."""
    s = get_settings()
    model = s.qwen_model
    import ollama as _ollama
    kwargs: Dict[str, Any] = {"model": model, "messages": [{"role": "user", "content": prompt}]}
    if tools:
        kwargs["tools"] = tools  # type: ignore
    resp = _ollama.chat(**kwargs)  # type: ignore
    msg = resp.get("message", {})
    raw = msg.get("content", "") or ""
    tcs = msg.get("tool_calls") or []
    return raw, tcs

# ---------- public calls ----------

def call_qwen_router(query: str, assets: list | None = None) -> Dict[str, Any]:
    prov = resolve_provider()
    s = get_settings()
    model = s.qwen_model
    prompt = f"""You are Satiq's router. The application ONLY handles geospatial work related to satellite imagery: water/land/forest/agriculture/buildings/urban/change detection/SAR/optical/NDVI/NDWI/spectral/vegetation etc.

Classify into ONE word, but be lenient for followups with image:
- greeting: short hi/hello/thanks/bye alone (no task)
- help: what can you do / how to use / capabilities
- chitchat: geospatial knowledge without image that IS within premises (what is NDVI? explain NDVI) — can answer as text
- out_of_scope: ONLY if clearly outside premises AND no image context — math/homework (solve 4x+3y), casual "how you doing" without image/geo, general non-geospatial. If query is vague like "provide info regarding the provided image" AND Has image is True, then it IS geospatial -> choose vqa
- vqa/grounding/change_vqa/optical_sar_fusion: needs image analysis (detect, where, how many, compare, SAR/optical, or vague "provide info" WITH image)

Query: "{query}"
Assets modalities: {[a.get('modality') for a in (assets or [])]}
Has image: {bool(assets)}
Answer with ONE word only from: vqa, grounding, change_vqa, optical_sar_fusion, greeting, chitchat, help, out_of_scope — if Has image is True and query mentions image/provided/that/this, prefer vqa over out_of_scope."""
    try:
        from orchestrator.helpers.tool_schemas import ROUTER_TOOLS, TOOL_NAME_TO_TASK
        raw, tcs = _call_ollama(prompt, tools=ROUTER_TOOLS)
        if tcs:
            tc = tcs[0]
            fname = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else getattr(tc.function, "name", "")
            if fname in TOOL_NAME_TO_TASK:
                tt = TOOL_NAME_TO_TASK[fname]
                if qwen_circuit is not None:
                    try: qwen_circuit.record_success()
                    except Exception: pass
                return {"task_type": tt, "reasoning": f"Ollama {model} tool {fname}->{tt}", "confidence": 0.92, "_provider": "local", "_model": model, "_tool_call": True}
    except Exception:
        pass
    import ollama as _ollama2
    resp = _ollama2.chat(model=model, messages=[{"role": "user", "content": prompt}])
    raw = resp.get("message", {}).get("content", "") or ""
    content = _strip_think(raw)
    import re as _re
    m = _re.search(r"\b(vqa|grounding|change_vqa|optical_sar_fusion|greeting|chitchat|help|out_of_scope)\b", content.lower())
    if m:
        tt = m.group(1)
        if qwen_circuit is not None:
            try: qwen_circuit.record_success()
            except Exception: pass
        return {"task_type": tt, "reasoning": f"Ollama {model} intent {tt}", "confidence": 0.90, "_provider": "local", "_model": model}
    raise RuntimeError(f"Ollama qwen3.5:9b router returned no valid task_type: {raw[:300]}")


def call_qwen_planner(query: str, task_type: str, assets: list | None = None) -> Dict[str, Any]:
    prov = resolve_provider()
    s = get_settings()
    rag_context = ""
    try:
        from orchestrator.services.conversation import load_history
        hist = load_history(task_type, n=2)  # type: ignore
        rag_context = f"Prior history snippets: {hist[:2]}" if hist else "No prior context"
    except Exception:
        rag_context = "No prior context"
    prompt = f"""You are a remote sensing task planner for SatQuery AI.
Decompose the user query into a structured execution plan.

SUPPORTED TASK TYPES ONLY: vqa, captioning, grounding, change_vqa, optical_sar_fusion
UNSUPPORTED (always REFUSE): forecasting, weather prediction, non-imagery tasks

SENSORS: Sentinel-1 (SAR), Sentinel-2 (optical), Cartosat-2S (panchromatic), RISAT-1 (SAR), Landsat-8/9, NASA HLS
SPECTRAL INDICES: NDVI, NDWI, NDBI — computed deterministically by pipeline, do NOT plan as model tasks

RULES:
- If context contains [RESOLVED:...] references, use them as ground-truth coordinates
- If SAR + optical both required → task_type=optical_sar_fusion
- If query is ambiguous about location → confidence_required=LOW, note ambiguity in plan
- If outside supported capabilities → task_type=REFUSE with reason
- OUTPUT: valid JSON matching GoalPlan schema only. No prose. No explanation.

PRIOR CONTEXT: {rag_context}
CURRENT QUERY: {query}
AVAILABLE ASSETS: {assets or []}
TASK HINT: {task_type}
Produce JSON with keys: task_type, reasoning, required_assets, fusion_needed, temporal_needed, confidence, bbox_hint, spectral_indices_needed, ffmpeg_crop_needed, confidence_required, refuse_reason"""
    model = s.qwen_model
    try:
        from orchestrator.helpers.tool_schemas import REGISTERED_TOOLS, TOOL_NAME_TO_TASK
        raw, tcs = _call_ollama(prompt, tools=REGISTERED_TOOLS)
        if tcs:
            tc = tcs[0]
            fname = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else getattr(tc.function, "name", "")
            if fname in TOOL_NAME_TO_TASK:
                tt = TOOL_NAME_TO_TASK[fname]
                if qwen_circuit is not None:
                    try: qwen_circuit.record_success()
                    except Exception: pass
                return {"task_type": tt, "reasoning": f"Planner tool {fname}->{tt}", "required_assets": [], "fusion_needed": tt == "optical_sar_fusion", "temporal_needed": tt == "change_vqa", "confidence": 0.86, "bbox_hint": None, "spectral_indices_needed": [], "ffmpeg_crop_needed": False, "confidence_required": "medium", "_provider": "local", "_model": model, "_tool_call": True}
    except Exception:
        pass
    import ollama as _ollama3
    resp = _ollama3.chat(model=model, messages=[{"role": "user", "content": prompt}])
    raw = resp.get("message", {}).get("content", "") or ""
    if qwen_circuit is not None:
        try: qwen_circuit.record_success()
        except Exception: pass
    jstr = _extract_json(raw)
    if not jstr:
        raise RuntimeError(f"Ollama planner returned no JSON: {raw[:400]}")
    data = json.loads(jstr)
    data.setdefault("task_type", task_type)
    data.setdefault("reasoning", f"Ollama planned {task_type}")
    data.setdefault("required_assets", [])
    data.setdefault("fusion_needed", task_type=="optical_sar_fusion")
    data.setdefault("temporal_needed", task_type=="change_vqa")
    data.setdefault("confidence", 0.8)
    data["_provider"] = "local"
    data["_model"] = model
    return data


def call_qwen_composer(query: str, task_output: Dict[str,Any], trace: list) -> str:  # noqa: C901
    prov = resolve_provider()
    s = get_settings()
    hist_snip = ""
    try:
        from orchestrator.services.conversation import load_history
        hist = load_history(task_output.get("session_id") or "", n=2)
        if hist:
            hist_snip = "\nRecent conversation:\n" + "\n".join([f"- Q: {h.get('query','')[:120]} -> {h.get('task_output',{}).get('answer_text','')[:120]}" for h in hist[-2:]])
    except Exception:
        hist_snip = ""
    prompt = f"""You are Satiq's geospatial response composer — you decide the entire presentation.

Query: {query}
Task type: {task_output.get('task','')}
Task output: {json.dumps(task_output)[:2200]}
Trace: {json.dumps(trace)[-800:]}
{hist_snip}
Conversation images: {task_output.get('image_id') or task_output.get('optical_image_id') or task_output.get('image_ids') or ''}

You control what the frontend renders. Decide per-response what to show:

 - Text: always elaborate as fully as possible — no 350 word cap, use all tokens needed (up to 2000+). Be specific to the query — DO NOT return generic water-body copy when the query asks about agriculture/cattle/caves. Use the task_output's detected_label/sector/bbox precisely. If the label is agricultural field, say so; if no caves, say none.
 - Thinking: you MAY include <think> reasoning if it helps transparency — no stripping, output think as is if system allows (user explicitly allowed).
 - BBox: include as `| BBox | [x,y,x,y] |` + `![bbox overlay](bbox://{{xyxy}})` ONLY for grounding tasks where bbox is present and relevant.
 - Chart: include ```chart block when task_output has meaningful multi-value data (per-category, per-modality). Otherwise omit.
 - Map/Image: if the user uploaded images, reference them with markdown `![uploaded image](image://{{image_id}})` so the frontend can render them inline.
 - Elaborate fully, grounded, no hallucinations. Cite confidence.
"""
    model = s.qwen_model
    import ollama as _ollama
    resp = _ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
    content = resp.get("message", {}).get("content", "") or ""
    if qwen_circuit is not None:
        try: qwen_circuit.record_success()
        except Exception: pass
    if not content:
        raise RuntimeError(f"Ollama qwen3.5:9b composer returned empty (task {task_output.get('task')})")
    return content


async def call_qwen_composer_stream(query: str, task_output: Dict[str,Any], trace: list):
    prov = resolve_provider()
    s = get_settings()
    hist_snip_s = ""
    try:
        from orchestrator.services.conversation import load_history as _lh
        hist_s = _lh(task_output.get("session_id") or "", n=2)
        if hist_s:
            hist_snip_s = "\nRecent conversation:\n" + "\n".join([f"- Q: {h.get('query','')[:120]} -> {h.get('task_output',{}).get('answer_text','')[:120]}" for h in hist_s[-2:]])
    except Exception:
        hist_snip_s = ""
    prompt = f"""You are Satiq's geospatial response composer — elaborate fully with no token cap (up to 2048 tokens).

Query: {query}
Task type: {task_output.get('task','')}
Task output: {json.dumps(task_output)[:2200]}
Trace: {json.dumps(trace)[-800:]}
{hist_snip_s}
Conversation images: {task_output.get('image_id') or task_output.get('optical_image_id') or task_output.get('image_ids') or ''}

You control what the frontend renders. Decide per-response what to show:

- Text: always elaborate as fully as possible — no 350 word limit, provide comprehensive analysis. Be specific — use detected_label/sector/bbox from task_output; do NOT hallucinate water when query is agriculture/cattle/caves.
- Thinking: you MAY include <think> reasoning — now allowed per user.
- BBox: include `| BBox | [x,y,x,y] |` + `![bbox overlay](bbox://{{xyxy}})` ONLY for grounding with bbox.
- Chart: include ```chart block when task_output has multi-value data (per-category, per-modality). Otherwise omit.
- Map/Image: reference uploaded images as `![uploaded image](image://{{image_id}})` when relevant.
- Elaborate fully, cite confidence.
"""
    model = s.qwen_model
    import ollama as _ollama_s
    stream = _ollama_s.chat(model=model, messages=[{"role": "user", "content": prompt}], stream=True)
    for chunk in stream:
        d = chunk.get("message", {}).get("content", "")
        if d:
            yield d
