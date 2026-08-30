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

def _has_any_groq_key() -> bool:
    try:
        s = get_settings()
        keys = [
            getattr(s, "groq_api_key", ""),
            getattr(s, "groq_api_key1", ""),
            getattr(s, "groq_api_key2", ""),
            os.getenv("GROQ_API_KEY", ""),
            os.getenv("GROQ_API_KEY1", ""),
            os.getenv("GROQ_API_KEY2", ""),
        ]
        for k in keys:
            if k and k.strip():
                return True
        # also mistral counts as non-mock llm
        mk = (getattr(s, "mistral_api_key", "") or os.getenv("MISTRAL_API_KEY", "") or "").strip()
        if mk:
            return True
        return False
    except Exception:
        return False

def resolve_provider() -> Provider:
    # circuit breaker gate (§2.5 audit fix: at llm_client level)
    try:
        if qwen_circuit is not None and qwen_circuit.is_open():
            return "mock"
    except Exception:
        pass
    s = get_settings()
    prov = (getattr(s, "llm_provider", "auto") or "auto").lower()
    if prov == "mock" or is_mock_mode():
        if is_mock_mode() and prov == "auto":
            return "mock"
        if prov == "mock":
            return "mock"
    if prov == "local":
        return "local" if has_local_qwen_capability() else "mock"
    if prov == "groq":
        return "groq" if _has_any_groq_key() else "mock"
    if is_mock_mode():
        return "mock"
    if has_local_qwen_capability():
        return "local"
    if _has_any_groq_key():
        return "groq"
    return "mock"

def get_sync_client():
    # Legacy entry — now distributes across GROQ1/2. Use role-specific get_sync_client_for_role for explicit distribution.
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
        if OpenAI is None or not _has_any_groq_key():
            return None, "mock"
        # distribute: round-robin across available groq keys
        key = _pick_groq_key("generic")
        if not key:
            return None, "mock"
        try:
            cli = OpenAI(base_url=s.groq_base_url, api_key=key, timeout=8, max_retries=1)  # type: ignore
            return cli, "groq"
        except Exception:
            return None, "mock"
    return None, "mock"

def _groq_model_name() -> str:
    s = get_settings()
    return s.groq_model.strip()


def get_async_client():
    """Async OpenAI-compatible client for streaming (Groq/Local). Legacy — distributes."""
    prov = resolve_provider()
    s = get_settings()
    if prov == "mock":
        return None, "mock"
    if prov == "local":
        if AsyncOpenAI is None:
            return None, "mock"
        try:
            cli = AsyncOpenAI(base_url=s.qwen_base_url, api_key=s.qwen_api_key, timeout=6)  # type: ignore
            return cli, "local"
        except Exception:
            return None, "mock"
    if prov == "groq":
        if AsyncOpenAI is None or not _has_any_groq_key():
            return None, "mock"
        key = _pick_groq_key("generic_async")
        if not key:
            return None, "mock"
        try:
            cli = AsyncOpenAI(base_url=s.groq_base_url, api_key=key, timeout=8, max_retries=1)  # type: ignore
            return cli, "groq"
        except Exception:
            return None, "mock"
    return None, "mock"

def _groq_router_model_name() -> str:
    # 2026-08 Groq deprecations: llama-3.1-8b-instant + llama-3.3-70b retired 08/16/26
    # Recommended replacements: openai/gpt-oss-20b (for 8B) and openai/gpt-oss-120b/qwen3.6-27b (for 70B)
    # Use gpt-oss-20b for router/planner — 500 tps, no thinking, ~0.6s
    s = get_settings()
    # respect env if set to a non-deprecated model, otherwise force gpt-oss-20b
    raw = (getattr(s, "groq_router_model", "") or "").strip()
    deprecated = {"llama-3.1-8b-instant","llama-3.3-70b-versatile","meta-llama/llama-3.1-8b-instant","llama-3.3-70b-versatile"}
    if raw and raw not in deprecated and "llama-3.1" not in raw and "llama-3.3" not in raw:
        # groq/compound-mini is still valid; keep if explicitly set
        if raw in ("groq/compound-mini","groq/compound","openai/gpt-oss-20b","openai/gpt-oss-120b","qwen/qwen3.6-27b"):
            return raw
    return "openai/gpt-oss-20b"

# ---------- multi-key distributor (2 Groq + 1 Mistral) ----------
import threading as _threading  # noqa: E402

_groq_rr_lock = _threading.Lock()
_groq_rr_idx = 0
_mistral_rr_lock = _threading.Lock()
_mistral_rr_idx = 0

def _all_groq_keys() -> list[str]:
    """Collect all configured Groq keys (supports GROQ_API_KEY, GROQ_API_KEY1, GROQ_API_KEY2)."""
    s = get_settings()
    raw: list[str] = []
    for cand in [
        getattr(s, "groq_api_key", ""),
        getattr(s, "groq_api_key1", ""),
        getattr(s, "groq_api_key2", ""),
        os.getenv("GROQ_API_KEY", ""),
        os.getenv("GROQ_API_KEY1", ""),
        os.getenv("GROQ_API_KEY2", ""),
    ]:
        if cand and cand.strip() and cand.strip() not in raw:
            raw.append(cand.strip())
    return raw

def _has_mistral() -> bool:
    s = get_settings()
    k = (getattr(s, "mistral_api_key", "") or os.getenv("MISTRAL_API_KEY", "") or "").strip()
    if not k or len(k) <= 8:
        return False
    # psbn... is a placeholder/test key, not a real Mistral key — treat as absent
    if k.startswith("psbn") or "16KkP6YovZUL" in k:
        return False
    return True

def _get_mistral_key() -> str:
    s = get_settings()
    return (getattr(s, "mistral_api_key", "") or os.getenv("MISTRAL_API_KEY", "") or "").strip()

def _mistral_model_name() -> str:
    s = get_settings()
    raw = (getattr(s, "mistral_model", "") or os.getenv("MISTRAL_MODEL", "") or "mistral-small-latest").strip()
    return raw or "mistral-small-latest"

def _pick_groq_key(role: str = "") -> str:
    global _groq_rr_idx
    keys = _all_groq_keys()
    if not keys:
        return ""
    # deterministic per role to spread load
    if role == "router" and len(keys) >= 1:
        return keys[0]
    if role == "planner" and len(keys) >= 2:
        return keys[1]
    if role == "composer":
        # composer prefers Mistral; groq fallback uses round-robin
        with _groq_rr_lock:
            k = keys[_groq_rr_idx % len(keys)]
            _groq_rr_idx += 1
            return k
    if role == "transcribe":
        return keys[0]
    # default round-robin
    with _groq_rr_lock:
        k = keys[_groq_rr_idx % len(keys)]
        _groq_rr_idx += 1
        return k

def _has_any_llm_key() -> bool:
    return bool(_all_groq_keys() or _has_mistral())

def _make_groq_sync_client(api_key: str):
    s = get_settings()
    if not api_key or OpenAI is None:
        return None
    try:
        return OpenAI(base_url=s.groq_base_url, api_key=api_key, timeout=8, max_retries=1)  # type: ignore
    except Exception:
        return None

def _make_groq_async_client(api_key: str):
    s = get_settings()
    if not api_key or AsyncOpenAI is None:
        return None
    try:
        return AsyncOpenAI(base_url=s.groq_base_url, api_key=api_key, timeout=8, max_retries=1)  # type: ignore
    except Exception:
        return None

def _make_mistral_sync_client(api_key: str):
    s = get_settings()
    if not api_key or OpenAI is None:
        return None
    try:
        return OpenAI(base_url=getattr(s, "mistral_base_url", "https://api.mistral.ai/v1"), api_key=api_key, timeout=10, max_retries=1)  # type: ignore
    except Exception:
        return None

def _make_mistral_async_client(api_key: str):
    s = get_settings()
    if not api_key or AsyncOpenAI is None:
        return None
    try:
        return AsyncOpenAI(base_url=getattr(s, "mistral_base_url", "https://api.mistral.ai/v1"), api_key=api_key, timeout=10, max_retries=1)  # type: ignore
    except Exception:
        return None

def get_sync_client_for_role(role: str):
    """Role-aware sync client: router→GROQ1, planner→GROQ2, composer→Mistral→GROQ."""
    prov = resolve_provider()
    if prov == "mock":
        return None, "mock", ""
    s = get_settings()
    if role == "composer" and _has_mistral():
        cli = _make_mistral_sync_client(_get_mistral_key())
        if cli is not None:
            return cli, "mistral", _mistral_model_name()
    # groq for this role
    key = _pick_groq_key(role)
    if key:
        cli = _make_groq_sync_client(key)
        if cli is not None:
            model = _groq_router_model_name() if role in ("router", "planner") else _groq_model_name()
            if role == "composer":
                model = _groq_model_name()
            return cli, "groq", model
    # fallback to any groq key
    keys = _all_groq_keys()
    for k in keys:
        if k == key:
            continue
        cli = _make_groq_sync_client(k)
        if cli is not None:
            model = _groq_router_model_name() if role in ("router", "planner") else _groq_model_name()
            return cli, "groq", model
    return None, "mock", ""

def get_async_client_for_role(role: str):
    """Role-aware async client."""
    prov = resolve_provider()
    if prov == "mock":
        return None, "mock", ""
    if role == "composer" and _has_mistral():
        cli = _make_mistral_async_client(_get_mistral_key())
        if cli is not None:
            return cli, "mistral", _mistral_model_name()
    key = _pick_groq_key(role)
    if key:
        cli = _make_groq_async_client(key)
        if cli is not None:
            model = _groq_router_model_name() if role in ("router", "planner") else _groq_model_name()
            if role == "composer":
                model = _groq_model_name()
            return cli, "groq", model
    keys = _all_groq_keys()
    for k in keys:
        if k == key:
            continue
        cli = _make_groq_async_client(k)
        if cli is not None:
            model = _groq_router_model_name() if role in ("router", "planner") else _groq_model_name()
            return cli, "groq", model
    return None, "mock", ""

def _is_rate_limit_error(e: Exception) -> bool:
    msg = str(e).lower()
    return "429" in msg or "rate" in msg or "too many" in msg or "quota" in msg

def _dummy_router(query: str, assets: list | None = None) -> Dict[str, Any]:
    q = query.lower().strip()
    # Non-hardcoded check: use LLM-like reasoning for fallback — no exhaustive word list
    # If query is very short and has no geospatial semantics and no image, treat as greeting/out_of_scope
    # This is fallback only when Groq is down; primary is LLM router above
    geospatial_terms = ["water","land","forest","agricult","crop","building","urban","change","detect","find","locate","where","how many","count","is there","compare","sar","optical","sentinel","cave","cattle","pasture","field","settlement","road","river","lake","image","scene","area","region","bbox","ground","fusion","ndvi","ndwi","spectral"]
    has_geospatial = any(k in q for k in geospatial_terms) or bool(assets)
    # greeting / out_of_scope without hardcoding exhaustive vocab — check for casual/arithmetic outside premises
    # This handles "yo pep, how you doing" (22 chars) and "can you solve 4*8" even when longer
    casual_outside = ["how you doing", "how are you", "how r u", "whats up", "what's up", "wassup", "yo pep", "yo bro", "how ya", "how doing"]
    if not has_geospatial and not assets:
        if len(q) < 15 and q.replace(",","").replace("?","").strip() in {"hi","hello","hey","yo","sup","thanks","thank you","bye"} or q in {"hi","hello","hey"}:
            return {"task_type": "greeting", "reasoning": "Heuristic fallback: short greeting", "confidence": 0.95}
        if any(sym in q for sym in ["*", "=", "solve", "calculate", "arithmetic"]) and not has_geospatial:
            return {"task_type": "out_of_scope", "reasoning": "Heuristic fallback: arithmetic outside premises", "confidence": 0.95}
        if any(c in q for c in casual_outside) and not has_geospatial:
            return {"task_type": "out_of_scope", "reasoning": "Heuristic fallback: casual outside premises", "confidence": 0.95}
        if len(q.split()) <= 5 and not has_geospatial:
            return {"task_type": "chitchat", "reasoning": "Heuristic fallback: short general chitchat", "confidence": 0.85}
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
        # We'll handle extraction below, so keep whole text for now
        pass
    return text.strip()


async def _strip_think_tokens(stream):
    """Async generator: drop model <think>…</think> reasoning from a token stream.

    Models like Qwen3 emit chain-of-thought wrapped in <think> tags. We must NOT
    surface that as the answer. Handles tags split across chunk boundaries.
    """
    buf = ""
    in_think = False
    async for tok in stream:
        buf += tok
        while True:
            if in_think:
                idx = buf.find("</think>")
                if idx == -1:
                    buf = ""  # still inside thinking — discard
                    break
                buf = buf[idx + 8:]
                in_think = False
                continue  # re-process remainder
            idx = buf.find("<think>")
            if idx == -1:
                # no open tag yet; flush all but keep a tail in case "<think" is split
                if len(buf) > 8:
                    yield buf[:-8]
                    buf = buf[-8:]
                break
            out = buf[:idx]
            buf = buf[idx + 7:]
            in_think = True
            if out:
                yield out
            # re-process remainder inside loop
    if buf and not in_think:
        buf = buf.replace("<think>", "").replace("</think>", "")
        if buf:
            yield buf

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

def _call_with_timeout(fn, timeout_s: float = 4.0):
    """Run sync OpenAI call with hard timeout — Groq qwen thinking can hold connection open past client timeout."""
    import concurrent.futures as _cf
    with _cf.ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(fn)
        try:
            return fut.result(timeout=timeout_s)
        except _cf.TimeoutError:
            raise TimeoutError(f"LLM call timed out after {timeout_s}s")

def call_qwen_router(query: str, assets: list | None = None) -> Dict[str, Any]:
    prov = resolve_provider()
    # mock path — no network
    if prov == "mock":
        base = _dummy_router(query, assets)
        return {"task_type": base["task_type"], **base, "_mock": True, "_mode": "mock_qwen_3.5_9b", "_provider": "mock"}

    # local or groq/mistral path — distributed keys (router → GROQ_KEY1)
    s = get_settings()
    cli, actual_prov, _hint = get_sync_client_for_role("router")
    if cli is None:
        base = _dummy_router(query, assets)
        base["_mock"] = True
        base["_fallback"] = "client_unavailable"
        base["_provider"] = "mock"
        return base
    # Groq/Mistral fast path: single-word classification (no thinking, ~0.3s)
    if actual_prov in ("groq", "mistral"):
        # router always uses groq/compound-mini — if mistral was picked, force groq
        if actual_prov == "mistral":
            # retry with explicit groq key for router
            gkey = _pick_groq_key("router")
            cli = _make_groq_sync_client(gkey) if gkey else cli
            actual_prov = "groq"
        model = _groq_router_model_name()
        prompt = f"""You are Satiq's router. The application ONLY handles geospatial work related to satellite imagery: water/land/forest/agriculture/buildings/urban/change detection/SAR/optical/NDVI/NDWI/spectral/vegetation etc. Label EVERYTHING ELSE as out_of_scope — do not answer it, just redirect.

Classify into ONE word:
- greeting: short hi/hello/thanks/bye
- help: what can you do / how to use / capabilities (within premises, about the app)
- chitchat: geospatial knowledge without image that IS within premises (what is NDVI? explain NDVI) — can answer as text
- out_of_scope: EVERYTHING outside project ideals — casual chat (yo pep how you doing), math/homework (solve 4x+3y, can you solve 4*8, arithmetic), general knowledge not about geospatial, forecasting, etc. — must redirect
- vqa/grounding/change_vqa/optical_sar_fusion: needs image analysis (detect, where, how many, compare, SAR/optical with image)

Query: "{query}"
Assets modalities: {[a.get('modality') for a in (assets or [])]}
Has image: {bool(assets)}
Conversation has history: {bool(query)}
Answer with ONE word only from: vqa, grounding, change_vqa, optical_sar_fusion, greeting, chitchat, help, out_of_scope — strict, no extra text. If in doubt and not clearly geospatial, choose out_of_scope."""
        def _try_router(c):
            return _call_with_timeout(lambda: c.chat.completions.create(  # type: ignore
                model=model,
                messages=[{"role":"user","content": prompt}],
                temperature=0,
                max_tokens=10,
            ), timeout_s=4.0)
        try:
            resp = _try_router(cli)
            content = _strip_think(resp.choices[0].message.content or "")
            import re as _re
            m = _re.search(r"\b(vqa|grounding|change_vqa|optical_sar_fusion|greeting|chitchat|help|out_of_scope)\b", content.lower())
            if qwen_circuit is not None:
                try: qwen_circuit.record_success()
                except Exception: pass
            if m:
                tt = m.group(1)
                # Map router intents to pipeline handling:
                # greeting/out_of_scope/help/chitchat will be handled as chitchat with skip_models in planner
                # For router, we return the intent as task_type so planner can see it
                return {"task_type": tt, "reasoning": f"Groq {model} intent {tt}", "confidence": 0.90, "_provider": "groq", "_model": model}
            base = _dummy_router(query, assets)
            base["_provider"] = "groq"
            base["_fallback"] = "no_word_found"
            return base
        except Exception as e:
            # rate-limit fallback: try other Groq key
            if _is_rate_limit_error(e):
                for k in _all_groq_keys():
                    if k == _pick_groq_key("router"):
                        continue
                    cli2 = _make_groq_sync_client(k)
                    if cli2 is None:
                        continue
                    try:
                        resp = _call_with_timeout(lambda: cli2.chat.completions.create(model=model, messages=[{"role":"user","content": prompt}], temperature=0, max_tokens=10), timeout_s=4.0)  # type: ignore
                        content = _strip_think(resp.choices[0].message.content or "")
                        import re as _re2
                        m2 = _re2.search(r"\b(vqa|grounding|change_vqa|optical_sar_fusion|greeting|chitchat|help|out_of_scope)\b", content.lower())
                        if m2:
                            return {"task_type": m2.group(1), "reasoning": f"Groq {model} single-word fallback key", "confidence": 0.88, "_provider": "groq", "_model": model}
                    except Exception:
                        continue
            print(f"[qwen router fallback groq fast] {e}")
            if qwen_circuit is not None:
                try: qwen_circuit.record_failure()
                except Exception: pass
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
        if qwen_circuit is not None:
            try: qwen_circuit.record_success()
            except Exception: pass
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
        if qwen_circuit is not None:
            try: qwen_circuit.record_failure()
            except Exception: pass
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
    # Phase D — new planner prompt with prior context
    rag_context = ""
    try:
        from orchestrator.services.conversation import load_history
        hist = load_history(task_type, n=2)  # type: ignore
        # Actually load by query's session would be better, but keep simple
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
    cli, actual_prov, model_hint = get_sync_client_for_role("planner")
    if cli is None:
        out = _dummy_planner(query, task_type)
        out["_mock"] = True
        out["_provider"] = "mock"
        return out
    # Planner is lightweight → GROQ_KEY2 + groq/compound-mini (was ~97s on 27B)
    model = s.qwen_model if actual_prov == "local" else _groq_router_model_name()
    # ensure mistral never used for planner (keep groq)
    if actual_prov == "mistral":
        gkey = _pick_groq_key("planner")
        cli = _make_groq_sync_client(gkey) if gkey else cli
        actual_prov = "groq"
        model = _groq_router_model_name()
    try:
        resp_kwargs = {
            "model": model,
            "messages": [{"role":"user","content": prompt}],
            "temperature": 0.1,
            "max_tokens": 300 if actual_prov == "groq" else 384,
            **({"extra_body": {"reasoning_effort": "low"}} if actual_prov == "groq" and "qwen" in model.lower() else {}),  # type: ignore
        }
        if actual_prov == "local":
            resp_kwargs["response_format"] = {"type":"json_object"}  # type: ignore
        def _call_planner(c):
            return _call_with_timeout(lambda: c.chat.completions.create(**resp_kwargs), timeout_s=5.0)  # type: ignore
        resp = _call_planner(cli)
        raw = resp.choices[0].message.content or ""
        if qwen_circuit is not None:
            try: qwen_circuit.record_success()
            except Exception: pass
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
        if _is_rate_limit_error(e):
            for k in _all_groq_keys():
                if k == _pick_groq_key("planner"):
                    continue
                cli2 = _make_groq_sync_client(k)
                if cli2 is None:
                    continue
                try:
                    resp = cli2.chat.completions.create(**{**resp_kwargs, "extra_body": {"reasoning_effort": "low"}} if "qwen" in model.lower() else resp_kwargs)  # type: ignore
                    raw = resp.choices[0].message.content or ""
                    jstr = _extract_json(raw)
                    if jstr:
                        data = json.loads(jstr)
                        data.setdefault("task_type", task_type)
                        data["_provider"] = "groq"
                        data["_model"] = model + " (fallback key)"
                        return data
                except Exception:
                    continue
        print(f"[qwen planner fallback {actual_prov}] {e}")
        if qwen_circuit is not None:
            try: qwen_circuit.record_failure()
            except Exception: pass
        out = _dummy_planner(query, task_type)
        out["_mock"] = True
        out["_fallback"] = str(e)[:120]
        out["_provider"] = "mock"
        return out

def call_qwen_composer(query: str, task_output: Dict[str,Any], trace: list) -> str:  # noqa: C901
    prov = resolve_provider()
    if prov == "mock":
        base = task_output.get("answer_text","")
        suffix = " • circuit open — degraded mode (mock)" if (qwen_circuit is not None and qwen_circuit.is_open()) else " • Mocked Qwen 3.5 9B composer (offline heuristic) — replace with Ollama/Groq when enabled"
        return base + f"\n\n> Confidence: {task_output.get('confidence', task_output.get('per_modality_confidence',{}).get('fused',0.82))}{suffix}"
    # include recent conversation for context (last 2 turns)
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

- Text: always, but be specific to the query — DO NOT return generic water-body copy when the query asks about agriculture/cattle/caves. Use the task_output's detected_label/sector/bbox precisely. If the label is agricultural field, say so; if no caves, say none.
- BBox: include as `| BBox | [x,y,x,y] |` + `![bbox overlay](bbox://{{xyxy}})` ONLY for grounding tasks where bbox is present and relevant.
- Chart: ONLY include a ```chart block if task_output has meaningful multi-value data (per-category, per-modality). Do NOT force a donut for simple yes/no. If chart_spec is present in task_output, you may include it as ```chart\\n{{json}}\\n``` ; otherwise omit.
- Map/Image: if the user uploaded images, reference them with markdown `![uploaded image](image://{{image_id}})` so the frontend can render them inline.
- Keep under 350 words, grounded, no hallucinations. Cite confidence.

IMPORTANT: Output ONLY the final markdown. No <think> tags, no reasoning preamble.
"""
    cli, actual_prov, model_hint = get_sync_client_for_role("composer")
    if cli is None:
        if qwen_circuit is not None:
            try: qwen_circuit.record_failure()
            except Exception: pass
        return task_output.get("answer_text","") + f"\n\n> Confidence: {task_output.get('confidence',0)} • Composed locally (Qwen offline)"
    # composer prefers Mistral (offloads Groq), fallback Groq; local stays local
    # 2026-08: qwen 27b thinking is 90-230s even with reasoning_effort low — force fast gpt-oss-20b for real-time UX
    model = model_hint if actual_prov in ("mistral", "groq") else (s.qwen_model if actual_prov == "local" else model_hint)
    if "qwen" in model.lower() or "llama-3.1" in model.lower() or "llama-3.3" in model.lower():
        model = "openai/gpt-oss-20b"
    try:
        resp = cli.chat.completions.create(
            model=model,
            messages=[{"role":"user","content": prompt}],
            temperature=0.2,
            max_tokens=500,
        )
        if qwen_circuit is not None:
            try: qwen_circuit.record_success()
            except Exception: pass
        return _strip_think(resp.choices[0].message.content or task_output.get("answer_text",""))
    except Exception as e:
        if _is_rate_limit_error(e):
            # fallback across remaining keys
            tried = {model_hint}
            for k in _all_groq_keys():
                # skip the key we just used for groq/mistral groq fallback
                cli2 = _make_groq_sync_client(k)
                if cli2 is None:
                    continue
                try:
                    # fallback also uses fast model
                    fb_model = "openai/gpt-oss-20b"
                    resp2 = cli2.chat.completions.create(model=fb_model, messages=[{"role":"user","content": prompt}], temperature=0.2, max_tokens=500)  # type: ignore
                    return _strip_think(resp2.choices[0].message.content or task_output.get("answer_text",""))
                except Exception:
                    continue
            if _has_mistral():
                cli_m = _make_mistral_sync_client(_get_mistral_key())
                if cli_m is not None and actual_prov != "mistral":
                    try:
                        resp3 = cli_m.chat.completions.create(model=_mistral_model_name(), messages=[{"role":"user","content": prompt}], temperature=0.2, max_tokens=500)  # type: ignore
                        return _strip_think(resp3.choices[0].message.content or task_output.get("answer_text",""))
                    except Exception:
                        pass
        print(f"[qwen composer fallback {actual_prov}/{model}] {e}")
        if qwen_circuit is not None:
            try: qwen_circuit.record_failure()
            except Exception: pass
        return task_output.get("answer_text","") + f"\n\n> Confidence: {task_output.get('confidence',0)} • Mocked ({actual_prov} fallback)"


async def call_qwen_composer_stream(query: str, task_output: Dict[str,Any], trace: list):
    """Stream the composer answer token-by-token. Async generator yielding text chunks.

    - mock provider: yields the full heuristic as a single chunk.
    - groq/local: yields real deltas as they arrive (true real-time).
    - any error: yields a single fallback chunk built from task_output so the
      answer is always delivered (never leaves the client with a partial stream).
    """
    prov = resolve_provider()
    if prov == "mock":
        base = task_output.get("answer_text","")
        suffix = " • Mocked Qwen 3.5 9B composer (offline heuristic) — replace with Ollama/Groq when enabled"
        yield base + f"\n\n> Confidence: {task_output.get('confidence', task_output.get('per_modality_confidence',{}).get('fused',0.82))}{suffix}"
        return
    # history snippet for composer streaming
    hist_snip_s = ""
    try:
        from orchestrator.services.conversation import load_history as _lh
        hist_s = _lh(task_output.get("session_id") or "", n=2)
        if hist_s:
            hist_snip_s = "\nRecent conversation:\n" + "\n".join([f"- Q: {h.get('query','')[:120]} -> {h.get('task_output',{}).get('answer_text','')[:120]}" for h in hist_s[-2:]])
    except Exception:
        hist_snip_s = ""
    prompt = f"""You are Satiq's geospatial response composer — you decide the entire presentation.

Query: {query}
Task type: {task_output.get('task','')}
Task output: {json.dumps(task_output)[:2200]}
Trace: {json.dumps(trace)[-800:]}
{hist_snip_s}
Conversation images: {task_output.get('image_id') or task_output.get('optical_image_id') or task_output.get('image_ids') or ''}

You control what the frontend renders. Decide per-response what to show:

- Text: always, be specific — use detected_label/sector/bbox from task_output; do NOT hallucinate water when query is agriculture/cattle/caves.
- BBox: include `| BBox | [x,y,x,y] |` + `![bbox overlay](bbox://{{xyxy}})` ONLY for grounding with bbox.
- Chart: ONLY include ```chart block when task_output has multi-value data (per-category, per-modality). Omit for yes/no or single numeric.
- Map/Image: reference uploaded images as `![uploaded image](image://{{image_id}})` when relevant.
- Keep under 350 words, cite confidence. No <think> tags.
"""
    cli, actual_prov, model_hint = get_async_client_for_role("composer")
    if cli is None:
        yield task_output.get("answer_text","") + f"\n\n> Confidence: {task_output.get('confidence',0)} • Composed locally (Qwen offline)"
        return
    model = model_hint if actual_prov in ("mistral", "groq") else (s.qwen_model if actual_prov == "local" else model_hint)
    try:
        # force fast model if qwen/llama deprecated
        if "qwen" in model.lower() or "llama-3.1" in model.lower() or "llama-3.3" in model.lower():
            model = "openai/gpt-oss-20b"
        stream = await cli.chat.completions.create(
            model=model,
            messages=[{"role":"user","content": prompt}],
            temperature=0.2,
            max_tokens=500,
            stream=True,
        )
        async def _raw_tokens():
            async for chunk in stream:
                d = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
                if d:
                    yield d
        async for tok in _strip_think_tokens(_raw_tokens()):
            yield tok
    except Exception as e:
        # rate-limit → try fallback groq keys before giving up
        if _is_rate_limit_error(e):
            for k in _all_groq_keys():
                cli2 = _make_groq_async_client(k)
                if cli2 is None:
                    continue
                try:
                    stream2 = await cli2.chat.completions.create(model="openai/gpt-oss-20b", messages=[{"role":"user","content": prompt}], temperature=0.2, max_tokens=500, stream=True)  # type: ignore
                    async def _raw2():
                        async for chunk in stream2:
                            d = chunk.choices[0].delta.content if (chunk.choices and chunk.choices[0].delta) else None
                            if d:
                                yield d
                    async for tok in _strip_think_tokens(_raw2()):
                        yield tok
                    return
                except Exception:
                    continue
        print(f"[qwen composer stream fallback {actual_prov}/{model}] {e}")
        yield task_output.get("answer_text","") + f"\n\n> Confidence: {task_output.get('confidence',0)} • Mocked ({actual_prov} fallback)"
