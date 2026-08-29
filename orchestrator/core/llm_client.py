"""LLM switch: local Qwen (Ollama) → Groq (qwen/qwen3.6-27b) → mock heuristic.

- LLM_PROVIDER=auto (default): try local Qwen if system can run it without crashing, else Groq if GROQ_API_KEY set, else mock.
- LLM_PROVIDER=local | groq | mock : force specific.
- MOCK_QWEN=true still forces mock for backward compat.
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import time
from typing import Dict, Any, Optional, Literal

try:
    from openai import OpenAI  # type: ignore
except Exception:
    OpenAI = None  # type: ignore

from .config import get_settings

# ---------- capability check for local Qwen ----------

def _ollama_binary() -> Optional[str]:
    return shutil.which("ollama")

def _ollama_has_model(model: str) -> bool:
    bin_path = _ollama_binary()
    if not bin_path:
        return False
    try:
        out = subprocess.run([bin_path, "list"], capture_output=True, text=True, timeout=4)
        txt = (out.stdout or "") + (out.stderr or "")
        # model name fuzzy: check prefix before colon
        base = model.split(":")[0].split("/")[-1].lower()
        return base in txt.lower() or model.lower() in txt.lower()
    except Exception:
        return False

def _system_can_run_qwen() -> bool:
    """Check RAM / CPU so we don't crash. Require ~4GB free for 7-9B quantized."""
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        # require at least 4GB available and not already swapping heavily
        if vm.available < 3.5 * 1024**3:
            return False
        # optional: check Ollama server responsiveness
        return True
    except Exception:
        # if psutil missing, assume can try
        return True

def has_local_qwen_capability() -> bool:
    s = get_settings()
    # must have ollama binary and model present or at least server reachable
    if not _ollama_binary():
        return False
    if not _system_can_run_qwen():
        return False
    # if model already pulled, definitely capability; else try ping server
    if _ollama_has_model(s.qwen_model):
        return True
    # fallback: try quick OpenAI ping with 3s timeout
    if OpenAI is None:
        return False
    try:
        cli = OpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=3)  # type: ignore
        # lightweight models list
        cli.models.list()  # type: ignore
        return True
    except Exception:
        return False

# ---------- provider resolution ----------

Provider = Literal["local", "groq", "mock"]

def is_mock_mode() -> bool:
    s = get_settings()
    if getattr(s, "mock_qwen", False):
        return True
    if os.getenv("MOCK_QWEN", "").lower() in ("1","true","yes"):
        return True
    return False

def resolve_provider() -> Provider:
    s = get_settings()
    prov = (getattr(s, "llm_provider", "auto") or "auto").lower()
    if prov == "mock" or is_mock_mode():
        # if explicit mock, keep mock; but auto would still try groq/local first unless MOCK_QWEN forced
        # For backward compat, MOCK_QWEN=true forces mock even in auto
        if is_mock_mode() and prov == "auto":
            # still allow groq if user set GROQ_API_KEY and no local capability?
            # New behavior: if MOCK_QWEN=true, respect it as force mock (user said mock qwen for now)
            # But new requirement says auto switch local→groq; so if MOCK_QWEN=true we stay mock
            return "mock"
        if prov == "mock":
            return "mock"
    if prov == "local":
        return "local" if has_local_qwen_capability() else "mock"
    if prov == "groq":
        return "groq" if s.groq_api_key else "mock"
    # auto
    if is_mock_mode():
        return "mock"
    if has_local_qwen_capability():
        return "local"
    if s.groq_api_key:
        return "groq"
    return "mock"

def get_sync_client():
    prov = resolve_provider()
    s = get_settings()
    if prov == "mock":
        return None, "mock"
    if prov == "local":
        if OpenAI is None:
            return None, "mock"
        try:
            cli = OpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=6)  # type: ignore
            return cli, "local"
        except Exception:
            return None, "mock"
    if prov == "groq":
        if OpenAI is None or not s.groq_api_key:
            return None, "mock"
        try:
            # Groq needs short timeout to fallback quickly to mock if slow
            cli = OpenAI(base_url=s.groq_base_url, api_key=s.groq_api_key, timeout=8)  # type: ignore
            return cli, "groq"
        except Exception:
            return None, "mock"
    return None, "mock"

def _groq_model_name() -> str:
    s = get_settings()
    return s.groq_model.strip()

def _groq_router_model_name() -> str:
    s = get_settings()
    return getattr(s, "groq_router_model", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"

def _dummy_router(query: str, assets: list | None = None) -> Dict[str, Any]:
    q = query.lower()
    has_opt = False
    has_sar = False
    if assets:
        for a in assets:
            m = (a.get("modality") or "").lower() if isinstance(a, dict) else str(a).lower()
            if m in ("optical","multispectral","s2"):
                has_opt = True
            if m in ("sar","s1"):
                has_sar = True
            aid = (a.get("asset_id") or a.get("id") or "") if isinstance(a, dict) else str(a)
            if "s1" in aid.lower() or "sar" in aid.lower():
                has_sar = True
            if "s2" in aid.lower() or "optical" in aid.lower():
                has_opt = True
    if any(k in q for k in ["change", "between", "what changed", "t1", "t2", "2018", "2023", "temporal"]):
        task = "change_vqa"
    elif any(k in q for k in ["fusion", "sar", "optical-sar", "optical_sar"]):
        task = "optical_sar_fusion"
    elif has_opt and has_sar and any(k in q for k in ["both images","both modalities","built-up and water","water-covered"]):
        task = "optical_sar_fusion"
    elif has_opt and has_sar and "identify" in q and "water" in q and "built" in q:
        task = "optical_sar_fusion"
    elif any(k in q for k in ["where", "locate", "bounding", "bbox", "ground", "water body", "building"]):
        task = "grounding"
    elif any(k in q for k in ["describe", "land-cover", "caption", "visible"]):
        task = "vqa"
    else:
        if "change" in q:
            task = "change_vqa"
        elif has_opt and has_sar:
            task = "optical_sar_fusion"
        elif "fusion" in q or "sar" in q:
            task = "optical_sar_fusion"
        elif "where" in q or "locate" in q:
            task = "grounding"
        else:
            task = "vqa"
    return {"task_type": task, "reasoning": f"Heuristic fallback for query: {query[:80]} assets_opt={has_opt} sar={has_sar}", "confidence": 0.78}

def _dummy_planner(query: str, task_type: str) -> Dict[str, Any]:
    return {
        "task_type": task_type,
        "reasoning": f"Planned {task_type} for query: {query[:80]}",
        "required_assets": [],
        "fusion_needed": task_type == "optical_sar_fusion",
        "temporal_needed": task_type == "change_vqa",
        "confidence": 0.82,
    }

# ---------- public calls ----------

def _strip_think(text: str) -> str:
    import re as _re
    # Groq Qwen thinking: <think> ... (often never closed, truncated) — remove from <think> to either </think> or to "Final string:" marker
    # First try closed tag
    if "</think>" in text:
        text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    else:
        # unclosed: remove from <think> to end, but keep final JSON after it if present via last JSON heuristic later
        # keep only after last "Final string:" or last "{" that is task_type JSON
        # For now just remove up to last occurrence of '{"task_type"'
        # We'll handle extraction below, so keep whole text for now
        pass
    return text.strip()

def _extract_json(text: str) -> str | None:
    import re as _re
    import json as _json
    # strip think tags if closed
    text = _re.sub(r"<think>.*?</think>", "", text, flags=_re.DOTALL)
    # If still has <think> unclosed, try to extract last JSON containing task_type
    # Find all candidate JSONs with task_type
    candidates = _re.findall(r"\{[^{}]*\"task_type\"[^{}]*\}", text, flags=_re.DOTALL)
    if candidates:
        # take last, try to load, if fails try to extract larger
        for cand in reversed(candidates):
            try:
                _json.loads(cand)
                return cand
            except Exception:
                continue
        return candidates[-1]
    # fallback: find all balanced brace JSONs via simple scan for last "{" to last "}"
    # Find last occurrence of '{"task_type"'
    idx = text.rfind('"task_type"')
    if idx != -1:
        start = text.rfind("{", 0, idx)
        # find matching closing } after start
        # use stack to find closing
        depth = 0
        end = -1
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    end = i+1
                    break
        if start != -1 and end != -1:
            return text[start:end]
    # last resort: first { to last }
    start = text.find("{")
    end = text.rfind("}")+1
    if start >=0 and end>start:
        return text[start:end]
    return None

def call_qwen_router(query: str, assets: list | None = None) -> Dict[str, Any]:
    prov = resolve_provider()
    # mock path — no network
    if prov == "mock":
        base = _dummy_router(query, assets)
        return {"task_type": base["task_type"], **base, "_mock": True, "_mode": "mock_qwen_3.5_9b", "_provider": "mock"}

    # local or groq path
    s = get_settings()
    cli, actual_prov = get_sync_client()
    if cli is None:
        base = _dummy_router(query, assets)
        base["_mock"] = True
        base["_fallback"] = "client_unavailable"
        base["_provider"] = "mock"
        return base
    # Groq fast path: single-word classification using llama (no thinking, 0.3s)
    if actual_prov == "groq":
        model = _groq_router_model_name()
        prompt = f"""Classify query into one word: vqa, grounding, change_vqa, optical_sar_fusion.
Query: "{query}"
Assets modalities: {[a.get('modality') for a in (assets or [])]}
Answer with one word only."""
        try:
            resp = cli.chat.completions.create(  # type: ignore
                model=model,
                messages=[{"role":"user","content": prompt}],
                temperature=0,
                max_tokens=10,
            )
            content = _strip_think(resp.choices[0].message.content or "")
            # extract single word
            import re as _re
            m = _re.search(r"\b(vqa|grounding|change_vqa|optical_sar_fusion)\b", content.lower())
            if m:
                tt = m.group(1)
                return {"task_type": tt, "reasoning": f"Groq qwen {model} single-word", "confidence": 0.90, "_provider": "groq", "_model": model}
            # fallback to dummy if no word found
            base = _dummy_router(query, assets)
            base["_provider"] = "groq"
            base["_fallback"] = "no_word_found"
            return base
        except Exception as e:
            print(f"[qwen router fallback groq fast] {e}")
            base = _dummy_router(query, assets)
            base["_mock"] = True
            base["_fallback"] = str(e)[:120]
            base["_provider"] = "mock"
            return base
    # local path (Ollama) — JSON mode
    model = s.qwen_model
    prompt = f"""You are Satiq's router. Classify the geospatial query into one task.
Tasks: vqa, grounding, change_vqa, optical_sar_fusion
Query: "{query}"
Assets: {assets or []}
Return JSON only, no <think>, no markdown, no explanation: {{"task_type": "...", "reasoning": "...", "confidence": 0.0-1.0}}"""
    try:
        resp = cli.chat.completions.create(  # type: ignore
            model=model,
            messages=[{"role":"user","content": prompt}],
            temperature=0.1,
            max_tokens=256,
            response_format={"type":"json_object"},  # type: ignore
        )
        raw = resp.choices[0].message.content or ""
        jstr = _extract_json(raw)
        if jstr:
            try:
                data = json.loads(jstr)
            except Exception as je:
                try:
                    fixed = jstr.replace("'", '"')
                    data = json.loads(fixed)
                except Exception:
                    raise je
            tt = data.get("task_type") or data.get("task") or "vqa"
            if tt not in ["vqa","grounding","change_vqa","optical_sar_fusion","captioning"]:
                tt = _dummy_router(query, assets)["task_type"]
                data["task_type"] = tt
            data["_provider"] = actual_prov
            data["_model"] = model
            return data
        base = _dummy_router(query, assets)
        base["_provider"] = actual_prov
        return base
    except Exception as e:
        print(f"[qwen router fallback {actual_prov}] {e}")
        base = _dummy_router(query, assets)
        base["_mock"] = True
        base["_fallback"] = str(e)[:120]
        base["_provider"] = "mock"
        return base

def call_qwen_planner(query: str, task_type: str, assets: list | None = None) -> Dict[str, Any]:
    prov = resolve_provider()
    if prov == "mock":
        out = _dummy_planner(query, task_type)
        out["_mock"] = True
        out["_mode"] = "mock_qwen_3.5_9b"
        out["_provider"] = "mock"
        return out
    s = get_settings()
    prompt = f"""You are Satiq's planner. Produce a StepPlan JSON.
Task: {task_type}
Query: "{query}"
Assets: {assets or []}
Return JSON only with keys: task_type, reasoning, required_assets (list), fusion_needed (bool), temporal_needed (bool), confidence (0-1)"""
    cli, actual_prov = get_sync_client()
    if cli is None:
        out = _dummy_planner(query, task_type)
        out["_mock"] = True
        out["_provider"] = "mock"
        return out
    model = s.qwen_model if actual_prov == "local" else _groq_model_name()
    try:
        resp_kwargs = {
            "model": model,
            "messages": [{"role":"user","content": prompt}],
            "temperature": 0.1,
            "max_tokens": 800 if actual_prov == "groq" else 384,
        }
        if actual_prov == "local":
            resp_kwargs["response_format"] = {"type":"json_object"}  # type: ignore
        resp = cli.chat.completions.create(**resp_kwargs)  # type: ignore
        raw = resp.choices[0].message.content or ""
        jstr = _extract_json(raw)
        if jstr:
            try:
                data = json.loads(jstr)
            except Exception as je:
                try:
                    fixed = jstr.replace("'", '"')
                    data = json.loads(fixed)
                except Exception:
                    raise je
            data.setdefault("task_type", task_type)
            data.setdefault("reasoning", f"Qwen planned {task_type}")
            data.setdefault("required_assets", [])
            data.setdefault("fusion_needed", task_type=="optical_sar_fusion")
            data.setdefault("temporal_needed", task_type=="change_vqa")
            data.setdefault("confidence", 0.82)
            data["_provider"] = actual_prov
            data["_model"] = model
            return data
        out = _dummy_planner(query, task_type)
        out["_provider"] = actual_prov
        return out
    except Exception as e:
        print(f"[qwen planner fallback {actual_prov}] {e}")
        out = _dummy_planner(query, task_type)
        out["_mock"] = True
        out["_fallback"] = str(e)[:120]
        out["_provider"] = "mock"
        return out

def call_qwen_composer(query: str, task_output: Dict[str,Any], trace: list) -> str:
    prov = resolve_provider()
    if prov == "mock":
        base = task_output.get("answer_text","")
        return base + f"\n\n> Confidence: {task_output.get('confidence', task_output.get('per_modality_confidence',{}).get('fused',0.82))} • Mocked Qwen 3.5 9B composer (offline heuristic) — replace with Ollama/Groq when enabled"
    s = get_settings()
    prompt = f"""You are Satiq's response composer. Fuse tool outputs into final answer.
Query: {query}
Task output: {json.dumps(task_output)[:2000]}
Trace: {json.dumps(trace)[-800:]}
Write concise markdown answer with > confidence, bbox if present, and evidence summary. Keep under 400 words."""
    cli, actual_prov = get_sync_client()
    if cli is None:
        return task_output.get("answer_text","") + f"\n\n> Confidence: {task_output.get('confidence',0)} • Composed locally (Qwen offline)"
    model = s.qwen_model if actual_prov == "local" else _groq_model_name()
    try:
        resp = cli.chat.completions.create(
            model=model,
            messages=[{"role":"user","content": prompt}],
            temperature=0.2,
            max_tokens=600,
        )
        return resp.choices[0].message.content or task_output.get("answer_text","")
    except Exception as e:
        print(f"[qwen composer fallback {actual_prov}] {e}")
        return task_output.get("answer_text","") + f"\n\n> Confidence: {task_output.get('confidence',0)} • Mocked Qwen (fallback {actual_prov})"
