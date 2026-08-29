"""Generate complete pipeline response file — runs all 5 task types through LangGraph and saves full state + final_result."""
import asyncio
import json
import time
from pathlib import Path
from orchestrator.models.graph_state import new_state
from orchestrator.graph.pipeline import get_pipeline
from orchestrator.core.config import get_settings
from orchestrator.core.llm_client import resolve_provider, has_local_qwen_capability

OUT_PATH = Path("orchestrator/complete_pipeline_response.json")
OUT_MD = Path("orchestrator/complete_pipeline_response.md")

CASES = [
    {
        "name": "vqa_open",
        "query": "Describe the land-cover and major objects visible in this image.",
        "assets": [{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bbox": [0,0,512,512], "bands": ["B02","B03","B04","B08"]}],
        "image_ids": ["img_001"],
        "sensor": "Sentinel-2",
        "expected_task": "vqa",
    },
    {
        "name": "grounding",
        "query": "Locate the water body in the northern sector",
        "assets": [{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "bands": ["B02","B03","B04"]}],
        "image_ids": ["img_001"],
        "expected_task": "grounding",
    },
    {
        "name": "change_vqa",
        "query": "What changed between these two dates, and where?",
        "assets": [
            {"asset_id": "img_2021", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04","B08"]},
            {"asset_id": "img_2023", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04","B08"]},
        ],
        "image_ids": ["img_2021","img_2023"],
        "sensor": "Sentinel-2 bi-temporal",
        "expected_task": "change_vqa",
    },
    {
        "name": "optical_sar_fusion",
        "query": "Identify built-up and water-covered regions using both images",
        "assets": [
            {"asset_id": "s2_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02","B03","B04","B08","B11"]},
            {"asset_id": "s1_001", "modality": "sar", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["VV","VH"], "sar_polarization": "VV+VH"},
        ],
        "image_ids": ["s2_001","s1_001"],
        "sensor": "Sentinel-1 + Sentinel-2",
        "expected_task": "optical_sar_fusion",
    },
    {
        "name": "captioning",
        "query": "Caption this image focusing on built-up and vegetation",
        "assets": [{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "bands": ["B02","B03","B04","B08"]}],
        "image_ids": ["img_001"],
        "expected_task": "vqa",
    },
    {
        "name": "followup_conversation",
        "query": "What about the northern region?",
        "assets": [{"asset_id": "img_2021", "crs": "EPSG:32617"}, {"asset_id": "img_2023", "crs": "EPSG:32617"}],
        "image_ids": ["img_2021","img_2023"],
        "session_id": "demo_followup_001",
        "note": "Followup after change_vqa — should inherit t1/t2 via conversation history",
        "expected_task": "change_vqa",
    },
    {
        "name": "sub_query_multi_part",
        "query": "Where changed AND how much did it change?",
        "assets": [{"asset_id": "img_2021", "crs": "EPSG:32617"}, {"asset_id": "img_2023", "crs": "EPSG:32617"}],
        "image_ids": ["img_2021","img_2023"],
        "expected_task": "change_vqa",
    },
    {
        "name": "region_geocoded",
        "query": "Describe change in Sector A",
        "assets": [{"asset_id": "img_2021", "crs": "EPSG:32617"}, {"asset_id": "img_2023", "crs": "EPSG:32617"}],
        "image_ids": ["img_2021","img_2023"],
        "expected_task": "change_vqa",
    },
]

async def run_all():
    get_settings.cache_clear()
    s = get_settings()
    provider = resolve_provider()
    has_local = has_local_qwen_capability()
    pipe = get_pipeline()
    results = []
    header = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": provider,
        "has_local_qwen": has_local,
        "llm_provider_setting": s.llm_provider,
        "mock_qwen": s.mock_qwen,
        "models": {"qwen": s.qwen_model, "groq": s.groq_model, "groq_router": getattr(s, "groq_router_model", "groq/compound-mini"), "stt": s.groq_stt_model},
        "voice_enabled": s.enable_voice,
        "note": "Complete pipeline response — each case includes full GraphState + final_result + execution_trace. Dummy vision (768/1024-d) swappable in dummy/*. See orchestrator/README.md",
    }
    for idx, case in enumerate(CASES):
        q = case["query"]
        assets = case["assets"]
        ids = case["image_ids"]
        sid = case.get("session_id") or f"complete_demo_{idx:02d}_{case['name']}"
        # for followup, preload history by saving previous change_vqa
        if case["name"] == "followup_conversation":
            # ensure history exists from previous change_vqa
            pass
        print(f"[{idx+1}/{len(CASES)}] {case['name']}: {q[:60]}")
        start = time.time()
        state = new_state(session_id=sid, query=q, assets=assets, image_ids=ids)
        # inject sensor hint for encoder_selector trace
        if case.get("sensor"):
            state["sensor_hint"] = case["sensor"]  # type: ignore
        out = await pipe.ainvoke(state)  # type: ignore
        elapsed = time.time() - start
        final = out.get("final_result") or out.get("task_output") or {}
        # build comprehensive record
        record = {
            "case": case["name"],
            "expected_task": case["expected_task"],
            "sensor": case.get("sensor"),
            "input": {"session_id": sid, "query": q, "assets": assets, "image_ids": ids},
            "routing": {
                "task_type": out.get("task_type"),
                "query_analysis": out.get("query_analysis"),
                "is_followup": out.get("is_followup"),
                "followup_anchor": out.get("followup_anchor"),
                "followup_resolved": out.get("followup_resolved"),
            },
            "plan": out.get("plan"),
            "region_of_interest": out.get("region_of_interest"),
            "sub_queries": out.get("sub_queries"),
            "encoder": out.get("encoder"),
            "coreg": out.get("coreg"),
            "coreg_passed": out.get("coreg_passed"),
            "requires_coreg": out.get("requires_coreg"),
            "spectral_indices": out.get("spectral_indices"),
            "tiles": out.get("tiles"),
            "embeddings_meta": {k: {"count": v.get("count"), "dim": v.get("dim")} if isinstance(v, dict) else str(type(v)) for k, v in (out.get("embeddings") or {}).items()},
            "fused_repr_meta": {"fusion_method": (out.get("fused_repr") or {}).get("fusion_method"), "confidence": (out.get("fused_repr") or {}).get("confidence"), "dim": (out.get("fused_repr") or {}).get("dim")},
            "task_output": out.get("task_output"),
            "final_result": final,
            "execution_trace": out.get("execution_trace"),
            "error_log": out.get("error_log"),
            "elapsed_s": round(elapsed, 3),
        }
        results.append(record)
        # save incremental for followup history
        if case["name"] == "change_vqa":
            try:
                from orchestrator.services.conversation import save_history
                save_history("demo_followup_001", {"session_id": sid, "query": q, "task_type": out.get("task_type"), "task_output": final, "task_output_id": sid})
            except Exception:
                pass

    payload = {"header": header, "cases": results}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote JSON: {OUT_PATH} ({OUT_PATH.stat().st_size/1024:.1f} KB)")

    # also write markdown human-readable
    md_lines = [f"# Complete Pipeline Response — Satiq\n\nGenerated: {header['generated_at']}\nProvider: `{header['provider']}` (local_qwen={header['has_local_qwen']}, llm_provider={header['llm_provider_setting']}, mock_qwen={header['mock_qwen']})\nModels: qwen=`{header['models']['qwen']}` groq=`{header['models']['groq']}` router=`{header['models']['groq_router']}` stt=`{header['models']['stt']}`\n", "Graph: `START → input_validator → router → planner → preprocessing → encoder_selector → encoder_compat → coreg_gate (bypass if requires_coreg=false) → vision_encoder → fusion → task_agent → tile_manager → post_processing → response_composer → END`\n", f"Dummy vision swappable in `dummy/` only — embeddings 768/1024-d seeded RNG, no real inference.\n"]
    for r in results:
        fr = r["final_result"] or {}
        md_lines.append(f"## {r['case']} — `{r['routing']['task_type']}` (expected `{r['expected_task']}`)\n")
        md_lines.append(f"- **Session:** `{r['input']['session_id']}` | **Sensor:** {r.get('sensor') or 'n/a'} | **Elapsed:** {r['elapsed_s']}s\n")
        md_lines.append(f"- **Query:** {r['input']['query']}\n")
        md_lines.append(f"- **Assets:** `{json.dumps(r['input']['assets'])}`\n")
        md_lines.append(f"- **Routing:** is_followup={r['routing'].get('is_followup')} anchor={r['routing'].get('followup_anchor')} analysis={json.dumps(r['routing'].get('query_analysis') or {}, default=str)[:300]}\n")
        md_lines.append(f"- **Plan:** `requires_coreg={r['requires_coreg']}` `encoder={r['encoder']}` `region={r['region_of_interest']}` `sub_queries={r['sub_queries']}`\n")
        md_lines.append(f"- **Coreg:** {json.dumps(r['coreg'], default=str)} passed={r['coreg_passed']} spectral={r.get('spectral_indices')}\n")
        md_lines.append(f"- **Tiles:** {len(r['tiles'] or [])} tiles\n")
        md_lines.append(f"- **Answer:** {fr.get('answer_text','')[:500]}\n")
        md_lines.append(f"- **Confidence:** {fr.get('confidence')} | **Numeric:** {fr.get('answer_numeric')} {fr.get('answer_unit')} | **Temporal:** {fr.get('answer_temporal_ref')}\n")
        if fr.get("bbox_xyxy"):
            md_lines.append(f"- **BBox xyxy:** {fr.get('bbox_xyxy')} normalized: {fr.get('bbox_normalized')}\n")
        if fr.get("change_categories"):
            md_lines.append(f"- **Change categories:** {fr.get('change_categories')} magnitude: {fr.get('change_magnitude_pct')}%\n")
        if fr.get("per_modality_confidence"):
            md_lines.append(f"- **Per-modality:** {fr.get('per_modality_confidence')}\n")
        if fr.get("chart_spec"):
            md_lines.append(f"- **Chart:** `{json.dumps(fr.get('chart_spec'))[:250]}`\n")
        if fr.get("followup_suggestions"):
            md_lines.append(f"- **Followups:** {fr.get('followup_suggestions')}\n")
        if fr.get("confidence_explanation"):
            md_lines.append(f"- **Confidence explanation:** {fr.get('confidence_explanation')}\n")
        md_lines.append(f"- **Trace:** {' → '.join([t['agent']+':'+t['status'] for t in (r['execution_trace'] or [])])}\n")
        if r.get("error_log"):
            md_lines.append(f"- **Error log:** {r['error_log']}\n")
        md_lines.append("\n")
    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Wrote MD: {OUT_MD} ({OUT_MD.stat().st_size/1024:.1f} KB)")
    return str(OUT_PATH), str(OUT_MD)

if __name__ == "__main__":
    import asyncio
    asyncio.run(run_all())
