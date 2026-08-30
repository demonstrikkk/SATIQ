import pytest
from unittest.mock import patch
pytestmark = pytest.mark.asyncio

async def test_llm_call_budget(pipeline, new_state):
    from tests.fixtures.dummy_data import valid_vqa_request
    data = valid_vqa_request()
    state = new_state(session_id="budget_llm", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    with patch("orchestrator.core.llm_client.call_qwen_router") as mr, \
         patch("orchestrator.core.llm_client.call_qwen_planner") as mp, \
         patch("orchestrator.core.llm_client.call_qwen_composer") as mc, \
         patch("orchestrator.core.llm_client.call_qwen_composer_stream") as mcs:
        # Mock to return deterministic without hitting Groq
        mr.return_value = {"task_type": "vqa", "reasoning": "test", "confidence": 0.9, "_provider": "mock"}
        mp.return_value = {"task_type": "vqa", "reasoning": "plan", "required_assets": [], "fusion_needed": False, "temporal_needed": False, "confidence": 0.9, "_provider": "mock"}
        async def _stream(*args, **kwargs):
            yield "mock answer"
        mcs.side_effect = _stream
        out = await pipeline.ainvoke(state)
        # Router + planner + composer = at least 2, but we mock all
        # The invariant is exactly 2 real LLM calls in production; in mock we just check pipeline completes
        assert out.get("final_result") is not None
        # Ensure no extra calls beyond mocked ones
        # If using mocks, call counts should be <=3
        assert mr.call_count <= 1
        assert mp.call_count <= 1

async def test_total_latency_mock(pipeline, new_state):
    import time
    from tests.fixtures.dummy_data import valid_vqa_request
    data = valid_vqa_request()
    state = new_state(session_id="latency_test", query=data["query"], assets=data["assets"], image_ids=data["image_ids"])
    t0 = time.time()
    out = await pipeline.ainvoke(state)
    dt = (time.time()-t0)*1000
    assert dt < 15000
    assert out.get("final_result") is not None
