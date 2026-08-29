"""CRS hard gate regression test — mismatched CRS must be rejected."""
from orchestrator.ingestion.validator import validate_crs_assets, validate_inputs
from orchestrator.agents.input_validator import input_validator_node
from orchestrator.models.graph_state import new_state

def test_crs_mismatch_rejected():
    assets = [
        {"asset_id":"a","crs":"EPSG:4326"},
        {"asset_id":"b","crs":"EPSG:3857"},
    ]
    ok, msg = validate_crs_assets(assets)
    assert not ok, "CRS mismatch should be rejected"
    assert "mismatch" in msg.lower()

def test_input_validator_hard_gate():
    state = new_state(session_id="test", query="describe image", assets=[
        {"asset_id":"a","crs":"EPSG:4326"},
        {"asset_id":"b","crs":"EPSG:3857"},
    ])
    out = input_validator_node(state)
    assert out["validation_passed"] is False
    assert "CRS mismatch" in (out.get("error") or "")

def test_valid_single_crs_passes():
    assets = [{"asset_id":"a","crs":"EPSG:32617"}, {"asset_id":"b","crs":"EPSG:32617"}]
    ok, _ = validate_crs_assets(assets)
    assert ok

def test_empty_query_fails():
    ok, msg = validate_inputs("", [], [])
    assert not ok

if __name__ == "__main__":
    test_crs_mismatch_rejected()
    test_input_validator_hard_gate()
    test_valid_single_crs_passes()
    test_empty_query_fails()
    print("validator tests PASSED")
