"""Cases 1,2 happy paths — must complete within ~15s, well-formed response."""
import pytest
import time
from tests.fixtures.dummy_data import valid_vqa_request, valid_change_vqa_request
from tests.conftest import record_latency_for_results

pytestmark = pytest.mark.asyncio

async def _run(pipeline, new_state, data):
    state = new_state(session_id=f"test_{int(time.time()*1000)}", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    # propagate _test_inject if present
    if "_test_inject" in data:
        state["_test_inject"] = data["_test_inject"]  # type: ignore
    t0 = time.time()
    out = await pipeline.ainvoke(state)  # type: ignore
    elapsed = int((time.time()-t0)*1000)
    return out, elapsed

async def test_valid_vqa(pipeline, new_state):
    data = valid_vqa_request()
    out, elapsed = await _run(pipeline, new_state, data)
    assert elapsed < 15000, f"budget exceeded {elapsed}ms"
    final = out.get("final_result")
    assert final is not None, "final_result missing"
    assert final.get("answer_text"), "answer_text empty"
    assert final.get("confidence") is not None
    assert 0 <= final["confidence"] <= 1
    # trace has latencies
    trace = out.get("execution_trace") or []
    assert any(t.get("agent")=="input_validator" for t in trace)
    record_latency_for_results(trace, "valid_vqa")

async def test_valid_change_vqa(pipeline, new_state):
    data = valid_change_vqa_request()
    out, elapsed = await _run(pipeline, new_state, data)
    assert elapsed < 15000
    final = out.get("final_result")
    assert final is not None
    # change tasks may have bbox or change info
    assert final.get("answer_text")
    trace = out.get("execution_trace") or []
    record_latency_for_results(trace, "valid_change_vqa")
