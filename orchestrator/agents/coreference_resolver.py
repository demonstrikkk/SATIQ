"""Coreference resolver — span-aware, structured, zero LLM calls (P1 hardening)."""
from __future__ import annotations
import re
import time
from typing import Dict, Any, List
from orchestrator.models.graph_state import GraphState, add_trace

# Keep short; "it" handled only via token boundary and structured refs, not substring
_PRONOUN_ALLOW = {"it", "this", "that"}

def _tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())

def _word_boundary_pattern(alias: str) -> re.Pattern:
    # Escape, require word boundaries, normalize whitespace inside alias
    parts = [re.escape(p) for p in alias.strip().split()]
    pat = r"\b" + r"\s+".join(parts) + r"\b"
    return re.compile(pat, re.IGNORECASE)

def _parse_resolution(resolution: str) -> Dict[str, Any]:
    # resolution like "bbox:[0.18,0.09,0.47,0.42]|ts:123" -> structured
    out: Dict[str, Any] = {"raw": resolution}
    try:
        if "bbox:" in resolution:
            # extract bbox list
            m = re.search(r"bbox:\s*\[([^\]]+)\]", resolution)
            if m:
                nums = [float(x.strip()) for x in m.group(1).split(",")]
                out["bbox"] = nums
                out["type"] = "asset_region"
            asset_m = re.search(r"asset:([^\s|]+)", resolution)
            if asset_m:
                out["asset_id"] = asset_m.group(1)
            ts_m = re.search(r"ts:([0-9\.]+)", resolution)
            if ts_m:
                out["timestamp"] = ts_m.group(1)
        elif "region:" in resolution:
            out["type"] = "region"
            out["region"] = resolution
    except Exception:
        pass
    return out

def coreference_resolver_node(state: GraphState) -> GraphState:
    t0 = time.time()
    query = state.get("query", "") or ""
    cr_map = state.get("coreference_map") or {}
    entity_reg = state.get("entity_registry") or {}
    all_refs: Dict[str, str] = {**entity_reg, **cr_map}  # entity_reg first, newer cr_map wins
    resolved = query
    structured_refs: List[Dict[str, Any]] = []
    # token set for fast reject before regex
    q_tokens = set(_tokenize(query))
    for alias, resolution in all_refs.items():
        alias_tokens = _tokenize(alias)
        if not alias_tokens:
            continue
        # span-aware: single pronoun "it" only matches isolated token, not substring ("within")
        if len(alias_tokens) == 1 and alias_tokens[0] in _PRONOUN_ALLOW:
            if alias_tokens[0] not in q_tokens:
                continue
        else:
            if not set(alias_tokens).issubset(q_tokens) and alias.lower() not in query.lower():
                # quick filter, still require regex for phrase
                pass
        pat = _word_boundary_pattern(alias)
        if not pat.search(query):
            continue
        # structured entity
        structured = _parse_resolution(str(resolution))
        structured["alias"] = alias
        structured["matched"] = True
        structured_refs.append(structured)
        # textual replacement for downstream LLM prompt, but keep structured in state
        resolved = pat.sub(f"[RESOLVED:{resolution}]", resolved)
    if resolved != query:
        state["query"] = resolved  # type: ignore
        state["query_original"] = query  # type: ignore
        state["resolved_entities"] = structured_refs  # type: ignore  # structured, not string
    else:
        state["resolved_entities"] = []  # type: ignore
    add_trace(state, "coreference_resolver", "ok", {"aliases": list(all_refs.keys()), "structured": structured_refs, "changed": resolved != query}, latency_ms=int((time.time()-t0)*1000))
    return state
