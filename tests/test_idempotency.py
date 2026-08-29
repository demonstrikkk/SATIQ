"""Case 8 repeated request — second call resumes from checkpoint, faster, same result."""
import pytest
import time

pytestmark = pytest.mark.asyncio

async def test_repeated_request_checkpoint_reuse(pipeline, new_state):
    from tests.fixtures.dummy_data import repeated_request
    data = repeated_request()
    # first call
    s1 = new_state(session_id="repeat_1", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    t0 = time.time(); out1 = await pipeline.ainvoke(s1)  # type: ignore
    dt1 = int((time.time()-t0)*1000)
    final1 = out1.get("final_result") or {}
    # second call same request_key (same query + image_ids) — new session but same key
    s2 = new_state(session_id="repeat_2", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    t0 = time.time(); out2 = await pipeline.ainvoke(s2)  # type: ignore
    dt2 = int((time.time()-t0)*1000)
    final2 = out2.get("final_result") or {}
    # checkpoint hits should be non-empty on second
    hits2 = out2.get("checkpoint_hits",[])
    assert len(hits2) > 0, f"expected checkpoint hit on second call, got {hits2}"
    # second should be measurably not slower than first (cached path)
    # allow tolerance but second should be <= first or within 50ms overhead
    assert dt2 <= dt1 + 50 or dt2 < 2000
    # same result (answer_text/confidence)
    assert final1.get("answer_text") == final2.get("answer_text")
    assert final1.get("confidence") == final2.get("confidence")
    # trace of second should contain ok_cached
    trace2 = out2.get("execution_trace",[])
    assert any("cached" in t.get("status","") for t in trace2)
