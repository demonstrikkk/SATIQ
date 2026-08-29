"""Run full pipeline end-to-end for each task type (no HTTP needed)."""
import asyncio
import json
from orchestrator.models.graph_state import new_state
from orchestrator.graph.pipeline import get_pipeline

CASES = [
    {"query":"Describe the land-cover and major objects visible in this image.", "image_ids":["img_001"], "assets":[{"asset_id":"img_001","modality":"optical","crs":"EPSG:32617","gsd":10}]},
    {"query":"Locate the water body in the northern sector", "image_ids":["img_001"], "assets":[{"asset_id":"img_001","modality":"optical","crs":"EPSG:32617"}]},
    {"query":"What changed between these two dates, and where?", "image_ids":["img_2021","img_2023"], "assets":[{"asset_id":"img_2021","modality":"optical","crs":"EPSG:32617"},{"asset_id":"img_2023","modality":"optical","crs":"EPSG:32617"}]},
    {"query":"Identify built-up and water-covered regions using both images", "image_ids":["s2_001","s1_001"], "assets":[{"asset_id":"s2_001","modality":"optical","crs":"EPSG:32617"},{"asset_id":"s1_001","modality":"sar","crs":"EPSG:32617"}]},
]

async def main():
    pipe = get_pipeline()
    for i, c in enumerate(CASES):
        print(f"\n=== Case {i+1}: {c['query'][:50]} ===")
        state = new_state(session_id=f"demo_{i}", query=c["query"], assets=c["assets"], image_ids=c["image_ids"])
        result = await pipe.ainvoke(state)
        final = result.get("final_result") or result.get("task_output")
        print(json.dumps({k:v for k,v in final.items() if k not in ("fused_repr","embeddings","_raw")}, indent=2)[:1200])
        print(f"trace: {[t['agent'] for t in result.get('execution_trace',[])]}")
        print(f"confidence: {result.get('confidence')}")

if __name__ == "__main__":
    asyncio.run(main())
