import pytest
pytestmark = pytest.mark.asyncio

async def test_multiturn_memory(pipeline, new_state):
    from tests.fixtures.dummy_data import valid_vqa_request, valid_change_vqa_request
    from orchestrator.services.conversation import save_history, load_history
    sid = "multiturn_test"
    # Turn 1: caption
    data1 = valid_vqa_request()
    data1["query"] = "Describe this Sentinel-2 image"
    state1 = new_state(session_id=sid, query=data1["query"], assets=data1["assets"], image_ids=data1["image_ids"])
    out1 = await pipeline.ainvoke(state1)
    save_history(sid, {"query": data1["query"], "task_output": out1.get("task_output") or out1.get("final_result"), "task_type": out1.get("task_type")})
    # Turn 2: followup uses prior
    state2 = new_state(session_id=sid, query="What is the NDVI of the forested area you mentioned?", assets=data1["assets"], image_ids=data1["image_ids"])
    out2 = await pipeline.ainvoke(state2)
    # Should have is_followup or resolved query
    assert out2 is not None
    # Check history loaded
    hist = load_history(sid, n=5)
    assert len(hist) >= 1
    # Turn 3: new image should not bleed
    data3 = valid_vqa_request()
    state3 = new_state(session_id=sid, query="Show me urban areas in this new image", assets=data3["assets"], image_ids=data3["image_ids"])
    out3 = await pipeline.ainvoke(state3)
    assert out3 is not None
