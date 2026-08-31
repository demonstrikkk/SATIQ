"""Full agentic pipeline test with REAL models (grounding + change hybrid) via model2 venv."""
import sys
from pathlib import Path

# Ensure SATIQ repo root on path
REPO_ROOT = Path(__file__).parent.resolve()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Ensure model repos on path (for capabilities to find train/config)
for p in [r"C:\coding\sih\model2_grounding", r"C:\coding\sih\model2_grounding\gdino_src", r"C:\coding\sih\model3_change_vqa"]:
    if p not in sys.path:
        sys.path.insert(0, p)

import asyncio
from orchestrator.models.graph_state import new_state
from orchestrator.graph.pipeline import get_pipeline

async def run_one(query, assets, ids):
    pipe = get_pipeline()
    state = new_state(session_id=f"test_{ids[0]}", query=query, assets=assets, image_ids=ids)
    # Set deadline 60s for real inference
    state["deadline_ms"] = 60000
    out = await pipe.ainvoke(state)
    return out

def print_result(name, out):
    print(f"\n{'='*60}\n{name}\n{'='*60}")
    print(f"task_type: {out.get('task_type')}")
    print(f"final_result task: {out.get('final_result',{}).get('task')}")
    print(f"answer_text: {out.get('final_result',{}).get('answer_text','')[:800]}")
    print(f"confidence: {out.get('final_result',{}).get('confidence')}")
    print(f"artifacts: {out.get('final_result',{}).get('artifacts')}")
    print(f"error: {out.get('final_result',{}).get('error') or out.get('error')}")
    trace = out.get('execution_trace', [])
    agents = [t['agent'] for t in trace]
    print(f"trace agents: {agents}")
    for t in trace:
        print(f"  {t['agent']:20} {t['status']:12} {t.get('detail',{})}")

# Real BigEarthNet patches
PATCH1 = r"C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_43_57"
PATCH2 = r"C:\coding\sih\BigEarthNet-S2\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP\S2A_MSIL2A_20170613T101031_N9999_R022_T33UUP_26_57"

# Test 1: Grounding with real patch
print("Running Grounding test with real S2 patch...")
out1 = asyncio.run(run_one(
    "Locate forest patch along western edge",
    [{"asset_id": PATCH1, "modality": "optical", "crs": "EPSG:32617"}],
    [PATCH1]
))
print_result("GROUNDING REAL", out1)

# Test 2: Change VQA with two real patches
print("\nRunning Change VQA test with two real patches...")
out2 = asyncio.run(run_one(
    "What changed between t1 and t2?",
    [{"asset_id": PATCH1, "crs": "EPSG:32617"}, {"asset_id": PATCH2, "crs": "EPSG:32617"}],
    [PATCH1, PATCH2]
))
print_result("CHANGE VQA REAL (hybrid)", out2)

# Test 3: VQA (will be MODEL_LOAD_ERROR - no VQA checkpoint, but should not hang)
print("\nRunning VQA test (expected MODEL_LOAD_ERROR - no VQA checkpoint)...")
out3 = asyncio.run(run_one(
    "Describe land cover",
    [{"asset_id": PATCH1, "modality": "optical", "crs": "EPSG:32617"}],
    [PATCH1]
))
print_result("VQA (no checkpoint)", out3)

print("\n=== ALL TESTS COMPLETE ===")
print("Check: grounding should have bbox_xyxy and confidence 0.7+, change should have stage1_index_hybrid metadata and no mock text")
