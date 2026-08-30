import pytest
pytestmark = pytest.mark.asyncio

def test_coreference_basic():
    from orchestrator.agents.coreference_resolver import coreference_resolver_node
    state = {
        "session_id": "test",
        "query": "What about that building?",
        "coreference_map": {"that building": "bbox:100,100,200,200"},
        "entity_registry": {},
        "execution_trace": [],
    }
    out = coreference_resolver_node(state)  # sync
    # Check if pipeline handles async vs sync
    import asyncio
    if asyncio.iscoroutine(out):
        out = asyncio.get_event_loop().run_until_complete(out)
    assert "[RESOLVED:bbox:100,100,200,200]" in out["query"]

def test_coreference_no_match():
    from orchestrator.agents.coreference_resolver import coreference_resolver_node
    state = {"session_id": "test", "query": "Where is water?", "coreference_map": {}, "entity_registry": {}, "execution_trace": []}
    out = coreference_resolver_node(state)
    import asyncio
    if asyncio.iscoroutine(out):
        out = asyncio.get_event_loop().run_until_complete(out)
    assert out["query"] == "Where is water?"

def test_entity_registry_precedence():
    from orchestrator.agents.coreference_resolver import coreference_resolver_node
    state = {
        "query": "that building height?",
        "coreference_map": {"that building": "old:1,1,2,2"},
        "entity_registry": {"that building": "bbox:100,100,200,200"},
        "execution_trace": [],
    }
    out = coreference_resolver_node(state)
    import asyncio
    if asyncio.iscoroutine(out):
        out = asyncio.get_event_loop().run_until_complete(out)
    assert "bbox:100,100,200,200" in out["query"]
