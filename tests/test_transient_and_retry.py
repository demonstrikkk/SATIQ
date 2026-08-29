"""Cases 6,7 transient — timeout enforcement + retry+checkpoint resume. No real sleep (audit #8)."""
import pytest
import time

pytestmark = pytest.mark.asyncio

async def test_slow_backend_timeout(pipeline, new_state):
    from tests.fixtures.dummy_data import slow_backend_request
    data = slow_backend_request("vision_encoder")
    state = new_state(session_id="slow_"+str(int(time.time()*1000)), query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    state["_test_inject"] = data["_test_inject"]  # type: ignore
    t0 = time.time()
    out = await pipeline.ainvoke(state)  # type: ignore
    elapsed = int((time.time()-t0)*1000)
    # must fire within budget, not hang — preprocessing is fast, vision timeout is immediate inject (no sleep)
    assert elapsed < 5000, f"should not actually sleep, got {elapsed}ms"
    # should have NodeTimeoutError path — either final error or retry loop then error
    trace = out.get("execution_trace",[])
    assert any(t.get("agent")=="vision_encoder" and t.get("status")=="failed" for t in trace)

async def test_flaky_backend_one_retry_success_no_redo(pipeline, new_state):
    from tests.fixtures.dummy_data import flaky_backend_request
    from orchestrator.core.checkpoint import has_checkpoint
    data = flaky_backend_request("vision_encoder")
    state = new_state(session_id="flaky_"+str(int(time.time()*1000)), query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    state["_test_inject"] = data["_test_inject"]  # type: ignore
    out = await pipeline.ainvoke(state)  # type: ignore
    # Exactly 1 retry occurs: retry_count should be 1
    assert out.get("retry_count",0) == 1, f"expected 1 retry got {out.get('retry_count')}"
    # checkpoint hit for preprocessing should be present (not redone)
    # after flaky, vision succeeded so overall should have final_result
    final = out.get("final_result")
    assert final is not None
    # verify preprocessing was checkpointed (second run would have hit if retried)
    # our pipeline's after_vision retry loops back to vision only, not preprocessing, so preprocessing not redone
    trace = out.get("execution_trace",[])
    # count vision failures =1, successes=1
    fails = [t for t in trace if t.get("agent")=="vision_encoder" and t.get("status")=="failed"]
    oks = [t for t in trace if t.get("agent")=="vision_encoder" and t.get("status") in ("ok","ok_cached")]
    assert len(fails)==1 and len(oks)==1
    # preprocessing should not repeat
    prep_nodes = [t for t in trace if t.get("agent")=="preprocessing"]
    assert len(prep_nodes)==1, "preprocessing should not be redone on vision retry (checkpoint)"

async def test_fusion_flaky_retry(pipeline, new_state):
    from tests.fixtures.dummy_data import flaky_backend_request
    data = flaky_backend_request("fusion")
    state = new_state(session_id="flaky_f_"+str(int(time.time()*1000)), query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    state["_test_inject"] = data["_test_inject"]  # type: ignore
    out = await pipeline.ainvoke(state)  # type: ignore
    assert out.get("retry_count",0)==1
    assert out.get("final_result") is not None
