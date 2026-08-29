"""Deterministic NLP pre-analysis before LLM router — feeds structured hints to reduce misroutes."""
from __future__ import annotations
import re
from typing import Dict, Any, List, Optional

# temporal: before/after, dates, year mentions
DATE_RE = re.compile(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2}|20\d{2}[-/]\d{1,2}|20\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+20\d{2})\b", re.I)
BEFORE_AFTER_RE = re.compile(r"\b(before|after|between|from|since|until|during|t1|t2|earlier|later|previous|next)\b", re.I)
CHANGE_VERBS = re.compile(r"\b(change|changed|expansion|shoreline|increase|decrease|growth|decline|urbanization|deforestation|flood)\b", re.I)

def detect_temporal_keywords(query: str) -> Dict[str, Any]:
    q = query.lower()
    date_mentions = DATE_RE.findall(query)
    # clean
    flat = []
    for d in date_mentions:
        if isinstance(d, tuple):
            flat.append(next((x for x in d if x), ""))
        else:
            flat.append(d)
    flat = [x for x in flat if x]
    has_before_after = bool(BEFORE_AFTER_RE.search(query))
    has_dates = len(flat) > 0
    has_change_verb = bool(CHANGE_VERBS.search(query))
    return {
        "has_before_after": has_before_after,
        "has_dates": has_dates,
        "has_change_verb": has_change_verb,
        "date_mentions": flat,
        "is_temporal": has_before_after or has_dates or has_change_verb,
    }

SPATIAL_RE = re.compile(r"\b(bbox|\[.*?,.*?,.*?,.*?\]|north|south|east|west|central|perimeter|sector|region|district|zone|area|basin|coast|shoreline)\b", re.I)
REGION_NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b")  # capital words
CAP_REGION_HINT = re.compile(r"\b(region|district|state|city|basin|sector|zone)\b", re.I)

def detect_spatial_keywords(query: str) -> Dict[str, Any]:
    q = query.lower()
    has_bbox = bool(re.search(r"\[\s*-?\d+\.?\d*\s*,\s*-?\d+\.?\d*\s*,", query))
    has_region_name = bool(CAP_REGION_HINT.search(query))
    # try to extract region candidate: look for "in <Region>" or capitalized near spatial hint
    region: Optional[str] = None
    m = re.search(r"\bin\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b", query)
    if m:
        region = m.group(1)
    elif has_region_name:
        # fallback: first capitalized phrase with 2 words
        caps = [x.strip() for x in REGION_NAME_RE.findall(query) if len(x.split())>=1]
        # filter common non-regions
        stop = {"What","Where","Describe","Identify","Show","Has","Is","Are","The","This","That"}
        cand = [c for c in caps if c not in stop and len(c) > 3]
        if cand:
            region = cand[0]
    has_spatial = bool(SPATIAL_RE.search(query)) or has_bbox or has_region_name
    return {
        "has_bbox_mention": has_bbox,
        "has_region_name": has_region_name,
        "region": region,
        "has_spatial": has_spatial,
    }

COMPARISON_RE = re.compile(r"\b(vs\.?|versus|compare|compared|difference|contrast|more than|less than|increase|decrease|larger|smaller|higher|lower)\b", re.I)

def detect_comparison_keywords(query: str) -> Dict[str, Any]:
    is_comparison = bool(COMPARISON_RE.search(query))
    # extract entities around comparison: look for "compare X and Y" or "X vs Y"
    entities: List[str] = []
    m = re.search(r"compare\s+(.+?)\s+and\s+(.+?)(?:\b|$)", query, re.I)
    if m:
        entities = [m.group(1).strip(), m.group(2).strip()]
    else:
        m2 = re.search(r"(.+?)\s+vs\.?\s+(.+?)(?:\b|$)", query, re.I)
        if m2:
            entities = [m2.group(1).strip(), m2.group(2).strip()]
    return {"is_comparison": is_comparison, "entities": entities}

FOLLOWUP_TRIGGERS = re.compile(r"\b(what about|how about|and the|that one|it|there|northern|southern|eastern|western|inside|within|surrounding|nearby|also|too)\b", re.I)
REF_PRONOUNS = re.compile(r"\b(it|that|there|this|that one|the same|previous|above)\b", re.I)

def detect_followup_intent(query: str, conversation_history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    q = query.lower()
    is_followup = False
    references_previous = False
    anchor_task_id: Optional[str] = None
    # heuristic: short query (<30 chars) or contains pronoun + history exists
    has_pronoun = bool(REF_PRONOUNS.search(query))
    has_trigger = bool(FOLLOWUP_TRIGGERS.search(query))
    if conversation_history and len(conversation_history) > 0:
        # if current query is short or has pronoun/trigger, treat as followup
        if has_pronoun or has_trigger or len(query.split()) <= 6:
            is_followup = True
            references_previous = has_pronoun or has_trigger
            anchor_task_id = conversation_history[-1].get("task_output_id") or conversation_history[-1].get("session_id")
    # also check explicit "that water body" -> followup
    if any(p in q for p in ["that ", "that water", "that region", "previous", "above "]):
        is_followup = True
        references_previous = True
        if conversation_history:
            anchor_task_id = conversation_history[-1].get("task_output_id")
    return {"is_followup": is_followup, "references_previous": references_previous, "anchor_task_id": anchor_task_id}
