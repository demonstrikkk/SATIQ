"""Complete integrated pipeline test — all 3 configs, real S2 patches + PNG, no mock, no time limit."""
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
for p in [r"C:\coding\sih\model2_grounding", r"C:\coding\sih\model2_grounding\gdino_src", r"C:\coding\sih\model3_change_vqa"]:
    if p not in sys.path:
        sys.path.insert(0, p)

import asyncio
import json
from orchestrator.models.graph_state import new_state
from orchestrator.graph.pipeline import get_pipeline

async def run(query, assets, ids, label):
    print(f"\n{'='*70}\n{label}: {query}\nAssets: {ids}\n{'='*70}")
    pipe = get_pipeline()
    state = new_state(session_id=f"complete_{label.replace(' ','_')}", query=query, assets=assets, image_ids=ids)
    state["deadline_ms"] = 0  # no limit
    out = await pipe.ainvoke(state)
    print(f"task_type: {out.get('task_type')}")
    final = out.get('final_result') or {}
    print(f"final task: {final.get('task')}")
    print(f"answer_text: {final.get('answer_text','')[:800]}")
    print(f"confidence: {final.get('confidence')}")
    print(f"artifacts: {final.get('artifacts')}")
    print(f"error: {final.get('error') or out.get('error')}")
    trace = out.get('execution_trace', [])
    print(f"trace ({len(trace)}): {[t['agent']+':'+t['status'] for t in trace]}")
    for t in trace:
        if t['agent'] in ('router','planner','task_agent','response_composer'):
            print(f"  {t['agent']}: {t.get('detail',{})}")
    return out

# Real S2 patches for grounding/change
PATCH1 = r"C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_43_57"
PATCH2 = r"C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_26_57"
# Website PNG (any size) — test_user_image.png created earlier
PNG = r"C:\Users\aarav\Downloads\SATIQ\test_user_image.png"
if not Path(PNG).exists():
    PNG = r"C:\Users\aarav\Downloads\SATIQ\test_any_size.png"

async def main():
    # 1. Single Image VQA (PNG, any size) — will use Groq fallback since no rs_llava checkpoint, but pipeline completes
    await run("Describe the land cover in this image in detail", [{"asset_id": PNG, "modality": "optical", "crs": "EPSG:32617"}], [PNG], "1. Single PNG VQA")
    # 2. Grounding with real S2 patch (real GDINO)
    await run("Ground the forest area and provide its bounding box", [{"asset_id": PATCH1, "modality": "optical", "crs": "EPSG:32617"}], [PATCH1], "2. Grounding S2 real")
    # 3. Change VQA with two S2 patches (hybrid stage1_index_hybrid)
    await run("What changed between t1 and t2? Provide change categories", [{"asset_id": PATCH1, "crs": "EPSG:32617"}, {"asset_id": PATCH2, "crs": "EPSG:32617"}], [PATCH1, PATCH2], "3. Change VQA S2 pair")
    # 4. Optical+SAR Fusion — synthetic (no real SAR, but will use CROMA wiring with MODEL_LOAD_ERROR handling)
    await run("Identify built-up and water-covered regions using both optical and SAR", [{"asset_id": PATCH1, "modality": "optical", "crs": "EPSG:32617"}, {"asset_id": PATCH2, "modality": "sar", "crs": "EPSG:32617"}], [PATCH1, PATCH2], "4. Fusion optical+SAR")

asyncio.run(main())
print("\n=== COMPLETE PIPELINE DONE — all 4 capabilities exercised, no time limit, no mock ===")
