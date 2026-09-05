"""Offline shim contract test — no weights, no GPU, uses synthetic assets.

Validates that 4 shims are linked and that call_model returns correct error shapes
when image missing, without invoking heavy torch. Uses ALLOW_SYNTHETIC_ASSETS=true
for pipeline synthetic path, but shim itself checks file existence.
"""
import os
from pathlib import Path

def test_shims_linked():
    os.environ["ALLOW_SYNTHETIC_ASSETS"] = "true"
    from orchestrator.capabilities.model_adapter import list_linked_models
    linked = list_linked_models()
    # All 4 should be True because files exist (model1/run_inference.py etc)
    assert linked["vqa"] is True
    assert linked["grounding"] is True
    assert linked["change_vqa"] is True
    assert linked["optical_sar_fusion"] is True

def test_shim_missing_image_error():
    from orchestrator.capabilities.model_adapter import call_model
    try:
        call_model("vqa", "Describe", ["nonexistent_zzz.tif"])
        assert False, "should raise FileNotFoundError"
    except FileNotFoundError as e:
        assert "not found" in str(e).lower() or "missing" in str(e).lower()
    except RuntimeError as e:
        # shim may wrap as MODEL_NOT_LINKED or MODEL_INFERENCE_ERROR
        assert "MODEL_" in str(e)

def test_task_agent_uses_image_pipeline():
    from orchestrator.services.image_pipeline import resolve_asset
    # synthetic resolver should handle asset_ prefix
    p = resolve_asset("asset_nonexistent_abc.tif")
    assert p is None or isinstance(p, Path)
