# Complete Pipeline Response — Satiq

Generated: 2026-08-29T10:40:37Z
Provider: `groq` (local_qwen=False, llm_provider=groq, mock_qwen=False)
Models: qwen=`qwen3.5:9b` groq=`qwen/qwen3.6-27b` router=`groq/compound-mini` stt=`whisper-large-v3`

Graph: `START → input_validator → router → planner → preprocessing → encoder_selector → encoder_compat → coreg_gate (bypass if requires_coreg=false) → vision_encoder → fusion → task_agent → tile_manager → post_processing → response_composer → END`

Dummy vision swappable in `dummy/` only — embeddings 768/1024-d seeded RNG, no real inference.

## vqa_open — `vqa` (expected `vqa`)

- **Session:** `complete_demo_00_vqa_open` | **Sensor:** Sentinel-2 | **Elapsed:** 5.563s

- **Query:** Describe the land-cover and major objects visible in this image.

- **Assets:** `[{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bbox": [0, 0, 512, 512], "bands": ["B02", "B03", "B04", "B08"]}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": false, "has_dates": false, "has_change_verb": false, "date_mentions": [], "is_temporal": false}, "spatial": {"has_bbox_mention": false, "has_region_name": false, "region": null, "has_spatial": false}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=False` `encoder=satmae` `region=None` `sub_queries=None`

- **Coreg:** {"ssim": 1.0, "residual": 0.0, "method": "dummy_affine", "passed": true, "num_tiles": 1} passed=True spectral=None

- **Tiles:** 1 tiles

- **Answer:** 
<think>
Thinking Process:

1.  **Deconstruct the Input:**
    *   Query: "Describe the land-cover and major objects visible in this image."
    *   Task Output: JSON object containing:
        *   `answer_text`: "The image shows a mix of agricultural fields in the center, a small settlement cluster to the east, and a forested patch along the western edge."
        *   `confidence`: 0.83
        *   `key_objects`: ["agricultural fields", "settlement", "forest"]
        *   `spatial_bbox`: null
 

- **Confidence:** 0.83 | **Numeric:** None None | **Temporal:** None

- **Chart:** `{"type": "donut", "title": "Land-cover confidence", "data": [{"name": "Agricultural Fields", "value": 0.83}, {"name": "Settlement", "value": 0.71}, {"name": "Forest", "value": 0.59}], "unit": "%", "note": "RS-VQA \u2022 data-driven"}`

- **Followups:** ['Count the built-up clusters?', 'Where is water relative to forest?', 'Generate a GeoJSON for this land-cover?']

- **Confidence explanation:** Moderate confidence — some ambiguity in tile evidence; coreg passed (SSIM≥0.75); encoder satmae.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:skipped → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## grounding — `grounding` (expected `grounding`)

- **Session:** `complete_demo_01_grounding` | **Sensor:** n/a | **Elapsed:** 12.557s

- **Query:** Locate the water body in the northern sector

- **Assets:** `[{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "bands": ["B02", "B03", "B04"]}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": false, "has_dates": false, "has_change_verb": false, "date_mentions": [], "is_temporal": false}, "spatial": {"has_bbox_mention": false, "has_region_name": true, "region": "Locate", "has_spatial": true}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=False` `encoder=satmae` `region=None` `sub_queries=None`

- **Coreg:** {"ssim": 1.0, "residual": 0.0, "method": "dummy_affine", "passed": true, "num_tiles": 1} passed=True spectral=None

- **Tiles:** 1 tiles

- **Answer:** 
<think>
Here's a thinking process:

1.  **Analyze User Input:**
   - **Role:** Satiq's response composer. Fuse tool outputs into final answer.
   - **Query:** Locate the water body in the northern sector
   - **Task Output:** JSON containing grounding results for image `img_001`.
     - `answer_text`: "Water body detected in the northern sector with confidence 0.89. BBox (normalized) [0.166, 0.076, 0.456, 0.406] corresponds to xyxy [120, 45, 310, 210]."
     - `bbox_normalized`: [0.166, 0.076, 

- **Confidence:** 0.89 | **Numeric:** 1.0 count | **Temporal:** None

- **BBox xyxy:** [120, 45, 310, 210] normalized: [0.166, 0.076, 0.456, 0.406]

- **Chart:** `{"type": "bar", "title": "Detection confidence", "data": [{"name": "Target", "value": 0.89}, {"name": "Background", "value": 0.11}], "unit": "confidence", "note": "Grounding"}`

- **Followups:** ['What is the area of this bbox in ha?', 'Show attention heatmap for this grounding?', 'Crop to this bbox and re-run VQA?']

- **Confidence explanation:** High confidence based on clear spectral contrast; coreg passed (SSIM≥0.75); encoder satmae.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:skipped → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## change_vqa — `change_vqa` (expected `change_vqa`)

- **Session:** `complete_demo_02_change_vqa` | **Sensor:** Sentinel-2 bi-temporal | **Elapsed:** 19.842s

- **Query:** What changed between these two dates, and where?

- **Assets:** `[{"asset_id": "img_2021", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02", "B03", "B04", "B08"]}, {"asset_id": "img_2023", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02", "B03", "B04", "B08"]}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": true, "has_dates": false, "has_change_verb": true, "date_mentions": [], "is_temporal": true}, "spatial": {"has_bbox_mention": false, "has_region_name": false, "region": null, "has_spatial": false}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=True` `encoder=prithvi` `region=None` `sub_queries=None`

- **Coreg:** {"ssim": 0.904, "residual": 0.26, "method": "dummy_affine", "passed": true, "num_tiles": 4} passed=True spectral=None

- **Tiles:** 4 tiles

- **Answer:** 
<think>
Here's a thinking process:

1.  **Analyze User Input:**
   - **Query:** "What changed between these two dates, and where?"
   - **Task Output:** JSON containing:
     - `answer_text`: "Built-up area has expanded along the eastern edge, replacing what was previously bare soil."
     - `change_categories`: ["built-up_increase"]
     - `change_magnitude_pct`: 14.8
     - `severity`: "moderate"
     - `confidence`: 0.83
     - `answer_numeric`: 14.8
     - `answer_unit`: "percent"
     - `a

- **Confidence:** 0.83 | **Numeric:** 14.8 percent | **Temporal:** 2021-2023

- **Change categories:** ['built-up_increase'] magnitude: 14.8%

- **Chart:** `{"type": "bar", "title": "Change by category (ha)", "data": [{"name": "built-up increase", "value": 22.14}], "unit": "ha", "note": "Change-VQA \u2022 per-category magnitude"}`

- **Followups:** ['Show built-up_increase magnitude as chart?', 'By how many ha did built-up increase per sector?', 'Show change mask as GeoJSON?']

- **Confidence explanation:** Moderate confidence — some ambiguity in tile evidence; coreg passed (SSIM≥0.75); encoder prithvi.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:ok → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## optical_sar_fusion — `optical_sar_fusion` (expected `optical_sar_fusion`)

- **Session:** `complete_demo_03_optical_sar_fusion` | **Sensor:** Sentinel-1 + Sentinel-2 | **Elapsed:** 19.977s

- **Query:** Identify built-up and water-covered regions using both images

- **Assets:** `[{"asset_id": "s2_001", "modality": "optical", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["B02", "B03", "B04", "B08", "B11"]}, {"asset_id": "s1_001", "modality": "sar", "crs": "EPSG:32617", "gsd": 10.0, "bands": ["VV", "VH"], "sar_polarization": "VV+VH"}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": false, "has_dates": false, "has_change_verb": false, "date_mentions": [], "is_temporal": false}, "spatial": {"has_bbox_mention": false, "has_region_name": false, "region": null, "has_spatial": false}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=True` `encoder=croma` `region=None` `sub_queries=None`

- **Coreg:** {"ssim": 0.929, "residual": 0.396, "method": "dummy_affine", "passed": true, "num_tiles": 4} passed=True spectral=None

- **Tiles:** 4 tiles

- **Answer:** 
<think>
Here's a thinking process:

1.  **Analyze User Input:**
   - **Role:** Satiq's response composer. Fuse tool outputs into final answer.
   - **Query:** Identify built-up and water-covered regions using both images
   - **Task Output:** JSON containing:
     - `task`: "optical_sar_fusion"
     - `query`: "Identify built-up and water-covered regions using both images"
     - `optical_image_id`: "s2_001"
     - `sar_image_id`: "s1_001"
     - `answer_text`: "The fused analysis shows built-u

- **Confidence:** 0.9 | **Numeric:** 0.9 confidence | **Temporal:** None

- **Per-modality:** {'optical': 0.83, 'sar': 0.78, 'fused': 0.9}

- **Chart:** `{"type": "bar", "title": "Modality confidence", "data": [{"name": "Optical", "value": 0.83}, {"name": "SAR", "value": 0.78}, {"name": "Fused", "value": 0.9}], "unit": "confidence", "note": "CROMA cross-attention \u2022 per-modality confidence"}`

- **Followups:** ['Which modality contributed more to water detection?', 'Export class map as GeoJSON?', 'Show per-tile confidence breakdown?']

- **Confidence explanation:** High confidence based on clear spectral contrast; coreg passed (SSIM≥0.75); encoder croma.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:ok → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## captioning — `vqa` (expected `vqa`)

- **Session:** `complete_demo_04_captioning` | **Sensor:** n/a | **Elapsed:** 18.16s

- **Query:** Caption this image focusing on built-up and vegetation

- **Assets:** `[{"asset_id": "img_001", "modality": "optical", "crs": "EPSG:32617", "bands": ["B02", "B03", "B04", "B08"]}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": false, "has_dates": false, "has_change_verb": false, "date_mentions": [], "is_temporal": false}, "spatial": {"has_bbox_mention": false, "has_region_name": false, "region": null, "has_spatial": false}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=False` `encoder=satmae` `region=None` `sub_queries=None`

- **Coreg:** {"ssim": 1.0, "residual": 0.0, "method": "dummy_affine", "passed": true, "num_tiles": 1} passed=True spectral=None

- **Tiles:** 1 tiles

- **Answer:** 
<think>
Here's a thinking process:

1.  **Analyze User Input:**
   - **Role:** Satiq's response composer
   - **Task:** Fuse tool outputs into final answer
   - **Query:** "Caption this image focusing on built-up and vegetation"
   - **Task Output:** JSON containing VQA results, including `answer_text`, `caption_text`, `key_objects`, `confidence`, `execution_trace`, etc.
   - **Constraints:** Concise markdown answer, include confidence, bbox if present, evidence summary, keep under 400 words.



- **Confidence:** 0.87 | **Numeric:** None None | **Temporal:** None

- **Chart:** `{"type": "donut", "title": "Land-cover confidence", "data": [{"name": "Agricultural Fields", "value": 0.87}, {"name": "Settlement", "value": 0.75}, {"name": "Forest", "value": 0.63}], "unit": "%", "note": "RS-VQA \u2022 data-driven"}`

- **Followups:** ['Count the built-up clusters?', 'Where is water relative to forest?', 'Generate a GeoJSON for this land-cover?']

- **Confidence explanation:** High confidence based on clear spectral contrast; coreg passed (SSIM≥0.75); encoder satmae.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:skipped → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## followup_conversation — `change_vqa` (expected `change_vqa`)

- **Session:** `demo_followup_001` | **Sensor:** n/a | **Elapsed:** 20.165s

- **Query:** What about the northern region?

- **Assets:** `[{"asset_id": "img_2021", "crs": "EPSG:32617"}, {"asset_id": "img_2023", "crs": "EPSG:32617"}]`

- **Routing:** is_followup=True anchor=complete_demo_02_change_vqa analysis={"temporal": {"has_before_after": true, "has_dates": false, "has_change_verb": false, "date_mentions": [], "is_temporal": true}, "spatial": {"has_bbox_mention": false, "has_region_name": true, "region": null, "has_spatial": true}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=True` `encoder=prithvi` `region=None` `sub_queries=None`

- **Coreg:** {"ssim": 0.924, "residual": 0.361, "method": "dummy_affine", "passed": true, "num_tiles": 4} passed=True spectral=None

- **Tiles:** 4 tiles

- **Answer:** 
<think>
Thinking Process:

1.  **Analyze the Request:**
    *   **Role:** Satiq's response composer.
    *   **Goal:** Fuse tool outputs into a final answer.
    *   **Query:** "What about the northern region?"
    *   **Context:** Previous image IDs `img_2021`, `img_2023`. Previous task `change_vqa`.
    *   **Task Output:**
        *   `answer_text`: "Built-up area has expanded along the eastern edge, replacing what was previously bare soil."
        *   `change_categories`: ["built-up_increa

- **Confidence:** 0.87 | **Numeric:** 13.0 percent | **Temporal:** 2021-2023

- **Change categories:** ['built-up_increase'] magnitude: 13.0%

- **Chart:** `{"type": "bar", "title": "Change by category (ha)", "data": [{"name": "built-up increase", "value": 19.45}], "unit": "ha", "note": "Change-VQA \u2022 per-category magnitude"}`

- **Followups:** ['Show built-up_increase magnitude as chart?', 'By how many ha did built-up increase per sector?', 'Show change mask as GeoJSON?']

- **Confidence explanation:** High confidence based on clear spectral contrast; coreg passed (SSIM≥0.75); encoder prithvi.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:ok → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## sub_query_multi_part — `change_vqa` (expected `change_vqa`)

- **Session:** `complete_demo_06_sub_query_multi_part` | **Sensor:** n/a | **Elapsed:** 19.038s

- **Query:** Where changed AND how much did it change?

- **Assets:** `[{"asset_id": "img_2021", "crs": "EPSG:32617"}, {"asset_id": "img_2023", "crs": "EPSG:32617"}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": false, "has_dates": false, "has_change_verb": true, "date_mentions": [], "is_temporal": true}, "spatial": {"has_bbox_mention": false, "has_region_name": false, "region": null, "has_spatial": false}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=True` `encoder=prithvi` `region=None` `sub_queries=['Where changed', 'how much did it change?']`

- **Coreg:** {"ssim": 0.885, "residual": 0.141, "method": "dummy_affine", "passed": true, "num_tiles": 4} passed=True spectral=None

- **Tiles:** 4 tiles

- **Answer:** 
<think>
Here's a thinking process:

1.  **Analyze User Input:**
   - **Role:** Satiq's response composer. Fuse tool outputs into final answer.
   - **Query:** "Where changed AND how much did it change?"
   - **Task Output:** JSON containing:
     - `task`: "change_vqa"
     - `query`: "Where changed AND how much did it change?"
     - `image_t1_id`: "img_2021", `image_t2_id`: "img_2023"
     - `answer_text`: "### Part 1\nBuilt-up area has expanded along the eastern edge, replacing what was prev

- **Confidence:** 0.77 | **Numeric:** 20.27 percent | **Temporal:** 2021-2023

- **Change categories:** ['built-up_increase'] magnitude: 20.27%

- **Chart:** `{"type": "bar", "title": "Change by category (ha)", "data": [{"name": "built-up increase", "value": 30.32}], "unit": "ha", "note": "Change-VQA \u2022 per-category magnitude"}`

- **Followups:** ['Show built-up_increase magnitude as chart?', 'By how many ha did built-up increase per sector?', 'Show change mask as GeoJSON?']

- **Confidence explanation:** Moderate confidence — some ambiguity in tile evidence; coreg passed (SSIM≥0.75); encoder prithvi.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:ok → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok



## region_geocoded — `change_vqa` (expected `change_vqa`)

- **Session:** `complete_demo_07_region_geocoded` | **Sensor:** n/a | **Elapsed:** 19.123s

- **Query:** Describe change in Sector A

- **Assets:** `[{"asset_id": "img_2021", "crs": "EPSG:32617"}, {"asset_id": "img_2023", "crs": "EPSG:32617"}]`

- **Routing:** is_followup=False anchor=None analysis={"temporal": {"has_before_after": false, "has_dates": false, "has_change_verb": true, "date_mentions": [], "is_temporal": true}, "spatial": {"has_bbox_mention": false, "has_region_name": true, "region": "Sector", "has_spatial": true}, "comparison": {"is_comparison": false, "entities": []}}

- **Plan:** `requires_coreg=True` `encoder=prithvi` `region={'region': 'Sector', 'bbox': [79.0, 12.0, 79.5, 12.5], 'crs': 'EPSG:4326'}` `sub_queries=None`

- **Coreg:** {"ssim": 0.922, "residual": 0.239, "method": "dummy_affine", "passed": true, "num_tiles": 4} passed=True spectral=None

- **Tiles:** 4 tiles

- **Answer:** 
<think>
Here's a thinking process:

1.  **Analyze User Input:**
   - **Role:** Satiq's response composer. Fuse tool outputs into final answer.
   - **Query:** Describe change in Sector A
   - **Task Output:** JSON containing:
     - `task`: "change_vqa"
     - `query`: "Describe change in Sector A"
     - `image_t1_id`: "img_2021"
     - `image_t2_id`: "img_2023"
     - `answer_text`: "Built-up area has expanded along the eastern edge, replacing what was previously bare soil."
     - `change_ca

- **Confidence:** 0.8 | **Numeric:** 12.61 percent | **Temporal:** 2021-2023

- **Change categories:** ['built-up_increase'] magnitude: 12.61%

- **Chart:** `{"type": "bar", "title": "Change by category (ha)", "data": [{"name": "built-up increase", "value": 18.86}], "unit": "ha", "note": "Change-VQA \u2022 per-category magnitude"}`

- **Followups:** ['Show built-up_increase magnitude as chart?', 'By how many ha did built-up increase per sector?', 'Show change mask as GeoJSON?']

- **Confidence explanation:** Moderate confidence — some ambiguity in tile evidence; coreg passed (SSIM≥0.75); encoder prithvi.

- **Trace:** input_validator:ok → router:ok → planner:ok → preprocessing:ok → encoder_selector:ok → encoder_compat:ok → coreg_gate:ok → vision_encoder:ok → fusion:ok → task_agent:ok → tile_manager:ok → post_processing:ok → response_composer:ok


