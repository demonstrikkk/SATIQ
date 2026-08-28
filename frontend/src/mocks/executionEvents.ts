import type { ExecutionEvent } from "@/schemas/execution";

const THINKING_COASTAL = `Analyzing request: “What changed along the eastern coastline?” — first turn, no history to resolve.
Input is bi-temporal (t1 2018, t2 2023), same AOI #004. Validating CRS EPSG:32617 and pairing.
Qwen 3.5 9B planner: coreference none, goals → change_vqa. Routing to M3: Change-VQA + change_map.`;

const THINKING_GROUNDING = `Query is “water body in the north” — grounding task.
Image img_001 (Sentinel-2). No crop needed, full scene. Referring expression = “water body”, bias to northern sector.
Routing to M2: GroundingDINO (bbox + optional SAM mask). Statistically water vs background.`;

const THINKING_FUSION = `User wants optical+SAR fusion over wetland. Need to co-register S1+S2, same AOI.
Per-modality confidence will show if SAR adds value. Routing to M4: CROMA cross-attention.`;

const THINKING_VQA = `Open VQA request: land-cover description. No bbox needed. This is a free-text VQA task.
Routing to M1: RS-VQA (open answer). Will describe fields, settlement, forest.`;

const THINKING_CROP = `Follow-up detected: “that small structure inside the northern edge of the detected water body”.
Resolving coreference: “that water body” → Turn1 bbox [120,45,310,210] (water body, 0.87).
Planner decides: crop ROI [120,45,310,210] via GIS/rasterio, then ground “structure” on the cropped tile.
Models stay stateless — GroundingDINO sees only the 190×165 tile, not history.`;

export function coastalChangeEvents(): ExecutionEvent[] {
  const block1 = `Significant coastal change was detected along the eastern and southeastern shoreline between 2018 and 2023.

### Key findings
- ~18.7 ha of shoreline retreat
- Highest change in sectors A and B
- Built-up expansion along the eastern edge

> Confidence: 0.87 • Area: 18.7 ha • Sensor: Sentinel-2 L2A`;

  const block2 = `\`\`\`chart
{"type":"bar","title":"Change by sector (ha)","data":[{"name":"Sector A","value":9.2},{"name":"Sector B","value":6.1},{"name":"Sector C","value":3.4}]}
\`\`\``;

  const block3 = `| Area | Change | Confidence |
|---|---:|---:|
| Sector A | 9.2 ha | 89% |
| Sector B | 6.1 ha | 82% |
| Sector C | 3.4 ha | 76% |`;

  const block4 = `![Before / After — 2018 vs 2023](comparison:2018-2023)`;

  const block5 = `![Change mask overlay](map:change-mask)

[View change area](#mock_bbox_001) [Open evidence](#evidence)`;

  return [
    { event: "query_started", payload: { query: "What changed along the eastern coastline?", llm: "qwen-3.5-9b" } },
    { event: "input_started" },
    { event: "input_done", payload: { status: "completed", durationMs: 110 } },
    { event: "planner_started" },
    { event: "planner_done", payload: { goal: "Detect coastal change 2018→2023", capabilities: ["change_vqa", "change_map"], spatial_target: "AOI #004", llm: "qwen-3.5-9b", goals: ["change_vqa"], crop_target: null, coreference_resolved: "none (first turn)", task_router_map: { change_vqa: "M3: Change-VQA" } } },
    { event: "execution_started", payload: { gis: { operation: "no-crop (full scene)", cropApplied: false } } },
    { event: "model_started", payload: { model: "ChangeChat" } },
    { event: "model_progress", payload: { progress: 0.45 } },
    { event: "model_done", payload: { model: "ChangeChat", confidence: 0.84, area_ha: 18.7, status: "OK", error_message: null, change_categories: ["built-up_increase"], answer_text: "Built-up area has expanded along the eastern edge, replacing what was previously bare soil." } },
    { event: "model_started", payload: { model: "GroundingDINO" } },
    { event: "model_done", payload: { model: "GroundingDINO", detections: 1, status: "OK", bbox_xyxy: [120,45,310,210], bbox_normalized: [0.18,0.09,0.47,0.42] } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.87, evidence_count: 3, units: "hectares" } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_COASTAL } },
    { event: "thinking_done" },
    { event: "answer_delta", payload: { chunk: block1 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block2 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block3 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block4 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block5 } },
    { event: "final_answer", payload: {} },
    { event: "query_completed" },
  ];
}

export function groundingEvents(): ExecutionEvent[] {
  const block1 = `Water body detected in the northern sector with high confidence.

> Confidence: 0.87 • Source: GroundingDINO • BBox: [0.18, 0.09, 0.47, 0.42] • BBox xyxy: [120, 45, 310, 210]`;

  const block2 = `![Detected water body — northern AOI](image:water-body)

[Water body · 87%](#mock_bbox_001) [Zoom to feature](#mock_bbox_001)`;

  const block3 = `| Property | Value |
|---|---|
| Label | Water body |
| BBox (normalized) | 0.18, 0.09, 0.47, 0.42 |
| BBox xyxy | 120, 45, 310, 210 |
| Confidence | 87% |
| Source | GroundingDINO |
| Status | OK |`;

  const block4 = `\`\`\`chart
{"type":"bar","title":"Detection confidence","data":[{"name":"Water","value":0.87},{"name":"Background","value":0.13}]}
\`\`\``;

  return [
    { event: "query_started", payload: { query: "Identify the water body in the north.", llm: "qwen-3.5-9b" } },
    { event: "input_started" },
    { event: "input_done", payload: { status: "completed", durationMs: 90 } },
    { event: "planner_started" },
    { event: "planner_done", payload: { goal: "Ground water body", capabilities: ["grounding"], llm: "qwen-3.5-9b", goals: ["grounding"], crop_target: null, coreference_resolved: "none", task_router_map: { grounding: "M2: Grounding (bbox + mask RLE)" } } },
    { event: "execution_started", payload: { gis: { operation: "no-crop", cropApplied: false } } },
    { event: "model_started", payload: { model: "GroundingDINO" } },
    { event: "model_done", payload: { model: "GroundingDINO", detections: 1, bbox_xyxy: [120,45,310,210], bbox_normalized: [0.18,0.09,0.47,0.42], mask_rle: null, confidence: 0.87, status: "OK", num_detections: 1 } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.87 } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_GROUNDING } },
    { event: "thinking_done" },
    { event: "answer_delta", payload: { chunk: block1 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block2 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block3 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block4 } },
    { event: "final_answer", payload: {} },
    { event: "query_completed" },
  ];
}

export function fusionEvents(query: string): ExecutionEvent[] {
  const block1 = `Optical **82%**, SAR **75%**, fused **88%**. Water and built-up are consistent across optical and SAR modalities.

> Per-modality confidence — optical 0.82 · sar 0.75 · fused 0.88 • Status: OK`;

  const block2 = `\`\`\`chart
{"type":"fusion","title":"Modality confidence","data":[{"name":"Optical","value":0.82},{"name":"SAR","value":0.75},{"name":"Fused","value":0.88}]}
\`\`\``;

  const block3 = `| Modality | Confidence |
|---|---:|
| Optical | 82% |
| SAR | 75% |
| Fused | 88% |`;

  const block4 = `![Optical vs SAR split view](comparison:optical-sar)

> Confidence: 0.88 • Fusion: CROMA cross-attention • Class map RLE: built-up / water / other

[Open comparison](comparison:optical-sar) [View evidence](#evidence)`;

  return [
    { event: "query_started", payload: { query, llm: "qwen-3.5-9b" } },
    { event: "input_started" },
    { event: "input_done", payload: { status: "completed", durationMs: 105 } },
    { event: "planner_started" },
    { event: "planner_done", payload: { goal: "Fuse optical+SAR", capabilities: ["fusion", "grounding"], llm: "qwen-3.5-9b", goals: ["optical_sar_fusion"], crop_target: null, task_router_map: { optical_sar_fusion: "M4: Optical-SAR Fusion (CROMA)" } } },
    { event: "execution_started", payload: { gis: { operation: "co-register S1+S2", cropApplied: false } } },
    { event: "model_started", payload: { model: "CROMA Fusion" } },
    { event: "model_done", payload: { model: "CROMA Fusion", confidence: 0.88, status: "OK", per_modality_confidence: { optical: 0.82, sar: 0.75, fused: 0.88 }, class_map_rle: { "built-up": "RLE_STRING_HERE", water: "RLE_STRING_HERE" } } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.88 } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_FUSION } },
    { event: "thinking_done" },
    { event: "answer_delta", payload: { chunk: block1 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block2 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block3 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block4 } },
    { event: "final_answer", payload: {} },
    { event: "query_completed" },
  ];
}

export function vqaEvents(): ExecutionEvent[] {
  const block0 = `![Selected image — img_001](image:img_001)

> Image: img_001 • Sentinel-2 • 10 m • Single-scene`;

  const block1 = `The image shows a mix of agricultural fields in the center, a small settlement cluster to the east, and a forested patch along the western edge.

> Confidence: 0.84 • Answer type: open • Image: img_001 • Status: OK`;

  const block2 = `| Field | Value |
|---|---|
| Task | vqa |
| Query | Describe the land-cover and major objects visible in this image. |
| Answer | Agricultural fields (center), settlement (east), forest (west) |
| Type | open |
| Confidence | 84% |`;

  const block3 = `\`\`\`chart
{"type":"bar","title":"Land-cover confidence","data":[{"name":"Agriculture","value":0.84},{"name":"Settlement","value":0.62},{"name":"Forest","value":0.71}]}
\`\`\``;

  return [
    { event: "query_started", payload: { query: "Describe the land-cover and major objects visible in this image.", llm: "qwen-3.5-9b" } },
    { event: "input_started" },
    { event: "input_done", payload: { status: "completed", durationMs: 80 } },
    { event: "planner_started" },
    { event: "planner_done", payload: { goal: "Describe land-cover", capabilities: ["vqa"], llm: "qwen-3.5-9b", goals: ["vqa"], crop_target: null, task_router_map: { vqa: "M1: RS-VQA (open/closed)" } } },
    { event: "execution_started", payload: { gis: { operation: "no-crop", cropApplied: false } } },
    { event: "model_started", payload: { model: "RS-VQA" } },
    { event: "model_done", payload: { model: "RS-VQA", status: "OK", answer_text: "The image shows a mix of agricultural fields in the center, a small settlement cluster to the east, and a forested patch along the western edge.", answer_type: "open", confidence: 0.84 } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.84 } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_VQA } },
    { event: "thinking_done" },
    { event: "answer_delta", payload: { chunk: block0 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block1 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block2 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block3 } },
    { event: "final_answer", payload: {} },
    { event: "query_completed" },
  ];
}

// Second turn: coreference + crop inside previous water body bbox
export function groundingCropSecondEvents(): ExecutionEvent[] {
  const block1 = `Inside the northern water body identified earlier **[120, 45, 310, 210]**, the high-resolution crop reveals a small building footprint along the northern perimeter.

> Cropped ROI: [120, 45, 310, 210] → tile 190×165 • Detected: building footprint • BBox (cropped tile): [15, 10, 45, 30] • Absolute: [135, 55, 165, 75] • Confidence: 0.89 • Status: OK`;

  const block2 = `![Cropped ROI — structure inside water body](image:structure-crop)

[Structure · 89%](#mock_bbox_002) [Zoom to crop](#mock_bbox_002)`;

  const block3 = `| Property | Value |
|---|---|
| Label | building footprint |
| BBox xyxy (crop tile) | 15, 10, 45, 30 |
| BBox xyxy (absolute) | 135, 55, 165, 75 |
| BBox normalized | 0.21, 0.11, 0.26, 0.14 |
| Source | GroundingDINO (cropped) |
| Confidence | 89% |`;

  return [
    { event: "query_started", payload: { query: "What is that small structure inside the northern edge of the detected water body?", llm: "qwen-3.5-9b" } },
    { event: "input_started" },
    { event: "input_done", payload: { status: "completed", durationMs: 95 } },
    { event: "planner_started" },
    {
      event: "planner_done",
      payload: {
        goal: "Ground structure inside previous water body",
        capabilities: ["grounding"],
        spatial_target: "crop [120,45,310,210]",
        llm: "qwen-3.5-9b",
        goals: ["crop", "grounding"],
        crop_target: [120, 45, 310, 210],
        coreference_resolved: "that water body -> Turn1 bbox [120,45,310,210] (water body, 0.87)",
        task_router_map: { crop: "GIS/rasterio engine", grounding: "M2: GroundingDINO (stateless, cropped tile)" },
      },
    },
    { event: "execution_started", payload: { gis: { operation: "rasterio crop [120,45,310,210] → reproject → tile", cropApplied: true, roi: "[120,45,310,210] 190×165" } } },
    { event: "model_started", payload: { model: "GroundingDINO (cropped)" } },
    { event: "model_done", payload: { model: "GroundingDINO", detections: 1, bbox_xyxy: [15,10,45,30], bbox_xyxy_absolute: [135,55,165,75], bbox_normalized: [0.21,0.11,0.26,0.14], label: "building footprint", confidence: 0.89, status: "OK", mask_rle: null } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.88, note: "Aggregated Turn1 water body (0.87) + Turn2 structure (0.89) → EvidenceGraph updated" } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_CROP } },
    { event: "thinking_done" },
    { event: "answer_delta", payload: { chunk: block1 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block2 } },
    { event: "answer_delta", payload: { chunk: "\n\n" + block3 } },
    { event: "final_answer", payload: {} },
    { event: "query_completed" },
  ];
}
