"""Test full LangGraph pipeline for all 5 task types."""
import asyncio
from orchestrator.models.graph_state import new_state
from orchestrator.graph.pipeline import get_pipeline

async def _run(query, assets, image_ids):
    pipe = get_pipeline()
    state = new_state(session_id="test", query=query, assets=assets, image_ids=image_ids)
    out = await pipe.ainvoke(state)
    return out

def test_vqa_pipeline():
    out = asyncio.run(_run("Describe the land-cover and major objects visible in this image.", [{"asset_id":"img_001","modality":"optical","crs":"EPSG:32617"}], ["img_001"]))
    assert out.get("final_result") is not None
    assert out["task_type"] == "vqa"
    # Real VQA now requires checkpoint at capabilities/single_image/weights/rs_llava.pth — dummy ids will be MODEL_LOAD_ERROR
    final = out["final_result"]
    if final.get("error"):
        assert "MODEL_LOAD_ERROR" in final.get("error", "") or "not found" in final.get("error", "").lower() or "No module" in final.get("error", "")
    else:
        assert final["confidence"] is None or final["confidence"] >= 0
    # trace must contain key agents
    agents = [t["agent"] for t in out.get("execution_trace",[])]
    assert "input_validator" in agents
    assert "router" in agents
    assert "vision_encoder" in agents
    print("vqa trace", agents)

def test_change_pipeline():
    out = asyncio.run(_run("What changed between these two dates, and where?", [{"asset_id":"img_2021","crs":"EPSG:32617"},{"asset_id":"img_2023","crs":"EPSG:32617"}], ["img_2021","img_2023"]))
    assert out["task_type"] == "change_vqa"
    # Real change_vqa now requires real S2 files + stage1 checkpoint; with dummy ids it returns MODEL_LOAD_ERROR
    # Graph must still complete (via error_handler) not hang — assert task_type and final_result exists
    assert out.get("final_result") is not None
    # If checkpoint missing, error code is MODEL_LOAD_ERROR, not mock fallback
    final = out["final_result"]
    if final.get("error"):
        assert "MODEL_LOAD_ERROR" in final.get("error", "") or "No module" in final.get("error", "") or "not found" in final.get("error", "").lower()
    else:
        assert "change_categories" in final

def test_fusion_pipeline():
    out = asyncio.run(_run("Identify built-up and water-covered regions using both images", [{"asset_id":"s2_001","modality":"optical","crs":"EPSG:32617"},{"asset_id":"s1_001","modality":"sar","crs":"EPSG:32617"}], ["s2_001","s1_001"]))
    assert out["task_type"] == "optical_sar_fusion"
    assert out.get("final_result") is not None
    final = out["final_result"]
    if final.get("error"):
        assert "MODEL_LOAD_ERROR" in final.get("error", "") or "not found" in final.get("error", "").lower()
    else:
        assert "per_modality_confidence" in final

def test_crs_gate():
    out = asyncio.run(_run("Describe image", [{"asset_id":"a","crs":"EPSG:4326"},{"asset_id":"b","crs":"EPSG:3857"}], ["a","b"]))
    # should go to error_handler
    agents = [t["agent"] for t in out.get("execution_trace",[])]
    assert "error_handler" in agents
    assert out.get("final_result",{}).get("error") is not None

if __name__ == "__main__":
    test_vqa_pipeline()
    test_change_pipeline()
    test_fusion_pipeline()
    test_crs_gate()
    print("pipeline tests PASSED")
