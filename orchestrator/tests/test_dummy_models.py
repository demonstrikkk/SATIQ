"""Test dummy models return correct-shaped outputs."""
from orchestrator.dummy.dummy_task_agents import dummy_vqa, dummy_grounding, dummy_change_vqa, dummy_optical_sar_fusion
from orchestrator.dummy.dummy_encoders import run_satmae, run_ssl4eo, run_prithvi
from orchestrator.dummy.dummy_fusion import run_fusion

def test_vqa_shape():
    out = dummy_vqa(None, "Describe the land-cover and major objects visible in this image.", "img_001")
    assert out["task"] == "vqa"
    assert "answer_text" in out
    assert 0 <= out["confidence"] <= 1

def test_grounding_shape():
    out = dummy_grounding(None, "Locate water", "img_001")
    assert out["task"] == "grounding"
    assert "bbox_xyxy" in out
    assert len(out["bbox_xyxy"]) == 4
    assert 0 <= out["confidence"] <= 1

def test_change_shape():
    out = dummy_change_vqa(None, "What changed between these two dates, and where?", "img_2021","img_2023")
    assert out["task"] == "change_vqa"
    assert "change_categories" in out
    assert isinstance(out["change_categories"], list)

def test_fusion_shape():
    out = dummy_optical_sar_fusion(None, "Identify built-up and water-covered regions using both images", "s2_001","s1_001")
    assert out["task"] == "optical_sar_fusion"
    assert "per_modality_confidence" in out
    assert "class_map_rle" in out
    assert all(k in out["per_modality_confidence"] for k in ["optical","sar","fused"])

def test_encoders():
    tiles = [{"tile_id":"t1"},{"tile_id":"t2"}]
    assert len(run_satmae(tiles)) == 2
    assert len(run_ssl4eo(tiles, "optical")) == 2
    assert len(run_prithvi(tiles)) == 2
    assert run_satmae(tiles)[0].shape[0] == 1024

def test_fusion():
    tiles = [{"tile_id":"t1"}]
    vecs = run_satmae(tiles)
    fused = run_fusion({"satmae": vecs}, "test query", method="attention")
    assert fused["fusion_method"] == "attention"
    assert 0 <= fused["confidence"] <= 1

if __name__ == "__main__":
    for fn in [test_vqa_shape, test_grounding_shape, test_change_shape, test_fusion_shape, test_encoders, test_fusion]:
        fn()
    print("dummy model tests PASSED")
