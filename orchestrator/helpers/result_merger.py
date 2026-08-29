"""Result merger for multi-part queries."""
from __future__ import annotations
from typing import List, Dict, Any

def merge_sub_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge sub-task results: min confidence, concat answer_texts with headers, merge bbox/category."""
    if not results:
        return {}
    # base is first
    merged = dict(results[0])
    if len(results) == 1:
        return merged
    # confidence = min
    confs = [r.get("confidence") for r in results if isinstance(r.get("confidence"), (int,float))]
    if confs:
        merged["confidence"] = min(confs)
    # also handle per_modality fused min
    for r in results[1:]:
        if r.get("per_modality_confidence"):
            base_per = merged.get("per_modality_confidence") or {}
            for k, v in r["per_modality_confidence"].items():
                if k not in base_per or v < base_per[k]:
                    base_per[k] = v
            merged["per_modality_confidence"] = base_per
    # answer_text concat with section headers
    texts = []
    for i, r in enumerate(results):
        t = r.get("answer_text","")
        if t:
            texts.append(f"### Part {i+1}\n{t}")
    if texts:
        merged["answer_text"] = "\n\n".join(texts)
    # bbox lists merge
    bboxes = []
    for r in results:
        if r.get("bbox_xyxy"):
            bboxes.append(r["bbox_xyxy"])
        if r.get("bbox_list"):
            bboxes.extend(r["bbox_list"])
        if r.get("bbox") and isinstance(r["bbox"], list) and len(r["bbox"])==4 and r not in bboxes:
            bboxes.append(r["bbox"])
    if bboxes:
        merged["bbox_list"] = bboxes
        merged["bbox"] = bboxes[0]
    # change_categories dedupe
    cats = []
    for r in results:
        for c in r.get("change_categories", []) or []:
            if c not in cats:
                cats.append(c)
    if cats:
        merged["change_categories"] = cats
    # numeric: take first non-null
    for k in ["answer_numeric","answer_unit","answer_temporal_ref"]:
        if merged.get(k) is None:
            for r in results[1:]:
                if r.get(k) is not None:
                    merged[k] = r[k]
                    break
    # phrase grounding map merge
    pgm = {}
    for r in results:
        if r.get("phrase_grounding_map"):
            pgm.update(r["phrase_grounding_map"])
    if pgm:
        merged["phrase_grounding_map"] = pgm
    merged["_merged_from"] = len(results)
    return merged
