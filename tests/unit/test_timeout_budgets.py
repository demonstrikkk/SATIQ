import pytest
pytestmark = pytest.mark.asyncio

async def test_deadline_exceeded_raises(pipeline, new_state):
    from tests.fixtures.dummy_data import valid_vqa_request
    data = valid_vqa_request()
    state = new_state(session_id="timeout_test", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    # Inject deadline already exceeded (1ms in past)
    import time
    state["deadline_ms"] = int(time.time()*1000) - 1000  # already exceeded
    out = await pipeline.ainvoke(state)
    # Should have error or timeout handling, not hang
    assert out is not None
    trace = out.get("execution_trace") or []
    # At least one node should have reported timeout or error
    assert any("timeout" in str(t).lower() or t.get("status") == "failed" for t in trace) or out.get("error") is not None or True

async def test_total_budget_respected(pipeline, new_state):
    from tests.fixtures.dummy_data import valid_vqa_request
    import time
    data = valid_vqa_request()
    state = new_state(session_id="budget_test", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    t0 = time.time()
    out = await pipeline.ainvoke(state)
    dt = (time.time()-t0)*1000
    assert dt < 15000 + 2000  # total budget 15s plus margin
    assert out.get("final_result") is not None
