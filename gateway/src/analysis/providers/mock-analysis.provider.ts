import type { AnalysisRequest, ExecutionEvent } from "../../../../shared/contracts";
import type { AnalysisProvider } from "./analysis-provider";

/**
 * MockAnalysisProvider — deterministic demo analysis engine.
 * STUB: emits scripted pipeline events (planner → models → evidence → composer).
 * This is the temporary stand-in for the future agentic pipeline; it is the
 * single source of demo truth (no component invents evidence anymore).
 */

const THINKING_COASTAL =
  "Qwen 3.5 9B planner: bi-temporal input (t1 2018, t2 2023), same AOI, CRS EPSG:32617 valid. " +
  "No coreference (first turn). Goals → change_vqa. Routing to M3: Change-VQA + change_map.";
const THINKING_GROUNDING =
  "Query is a grounding task. Referring expression = water body, bias to northern sector. " +
  "No crop needed (full scene). Routing to M2: GroundingDINO (bbox + optional SAM mask).";
const THINKING_FUSION =
  "Optical+SAR fusion over wetland. Co-register S1+S2, same AOI. " +
  "Routing to M4: CROMA cross-attention. Per-modality confidence will show SAR contribution.";
const THINKING_VQA =
  "Open VQA request: land-cover description. No bbox needed. Routing to M1: RS-VQA (open answer).";
const THINKING_CROP =
  "Follow-up detected: coreference resolved to Turn1 bbox [120,45,310,210] (water body, 0.87). " +
  "Planner decides: crop ROI via GIS/rasterio, then ground on the cropped tile. Models stay stateless.";

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    if (signal.aborted) return reject(new DOMException("Aborted", "AbortError"));
    const t = setTimeout(() => {
      signal.removeEventListener("abort", onAbort);
      resolve();
    }, ms);
    const onAbort = () => {
      clearTimeout(t);
      reject(new DOMException("Aborted", "AbortError"));
    };
    signal.addEventListener("abort", onAbort, { once: true });
  });

export class MockAnalysisProvider implements AnalysisProvider {
  readonly name = "mock";

  async *execute(request: AnalysisRequest, signal: AbortSignal): AsyncGenerator<ExecutionEvent> {
    const query = (request.query ?? "").toLowerCase().trim();
    const scenario = pickScenario(query);

    const events = buildScenarioEvents(scenario, request.query);

    for (const ev of events) {
      if (signal.aborted) return;
      // Pacing: fast for status events, slower for content chunks.
      const delay =
        ev.event === "thinking_delta"
          ? 240
          : ev.event === "answer_delta"
            ? 420
            : ev.event === "model_done" || ev.event === "planner_done"
              ? 500
              : 90;
      await sleep(delay, signal);
      yield { ...ev, timestamp: Date.now() };
    }
  }
}

type Scenario = "coastal" | "grounding" | "fusion" | "vqa" | "crop";

function pickScenario(q: string): Scenario {
  const isFollowUp = /structure|building|inside|that |northern edge|small|surrounding/.test(q);
  const isVqa = /describe|land.cover|agricultural|fields|settlement|forested|what is visible|visible in this image/i.test(q);
  const isGrounding = /water|structure|building|bbox|ground|locate agricultural/i.test(q);
  const isChange = /change|coast|urban|expansion|shoreline|built-up.*increased/i.test(q);
  const isFusion = /sar|fusion|optical.*sar|sar.*optical|compare.*optical.*sar/i.test(q);

  if (isFollowUp) return "crop";
  if (isVqa && !isGrounding && !isChange && !isFusion) return "vqa";
  if (isGrounding && !isChange) return "grounding";
  if (isFusion) return "fusion";
  return "coastal";
}

function buildScenarioEvents(scenario: Scenario, rawQuery: string): ExecutionEvent[] {
  switch (scenario) {
    case "grounding":
      return groundingEvents(rawQuery);
    case "fusion":
      return fusionEvents(rawQuery);
    case "vqa":
      return vqaEvents(rawQuery);
    case "crop":
      return cropEvents(rawQuery);
    case "coastal":
    default:
      return coastalEvents(rawQuery);
  }
}

function base(query: string): ExecutionEvent[] {
  return [
    { event: "query_started", payload: { query, llm: "qwen-3.5-9b" } },
    { event: "input_started" },
    { event: "input_done", payload: { status: "completed", durationMs: 110 } },
    { event: "planner_started" },
  ];
}

function coastalEvents(query: string): ExecutionEvent[] {
  return [
    ...base(query),
    {
      event: "planner_done",
      payload: {
        goal: "Detect coastal change 2018→2023",
        capabilities: ["change_vqa", "change_map"],
        spatial_target: "AOI #004",
        llm: "qwen-3.5-9b",
        goals: ["change_vqa"],
        crop_target: null,
        coreference_resolved: "none (first turn)",
        task_router_map: { change_vqa: "M3: Change-VQA" },
      },
    },
    { event: "execution_started", payload: { gis: { operation: "no-crop (full scene)", cropApplied: false } } },
    { event: "model_started", payload: { model: "ChangeChat" } },
    { event: "model_progress", payload: { progress: 0.45 } },
    {
      event: "model_done",
      payload: {
        model: "ChangeChat",
        confidence: 0.84,
        area_ha: 18.7,
        status: "OK",
        error_message: null,
        change_categories: ["built-up_increase"],
        answer_text: "Built-up area has expanded along the eastern edge, replacing what was previously bare soil.",
      },
    },
    { event: "model_started", payload: { model: "GroundingDINO" } },
    { event: "model_done", payload: { model: "GroundingDINO", detections: 1, status: "OK", bbox_xyxy: [120, 45, 310, 210], bbox_normalized: [0.18, 0.09, 0.47, 0.42] } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.87, evidence_count: 3, units: "hectares" } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_COASTAL } },
    { event: "thinking_done" },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "Significant coastal change was detected along the eastern and southeastern shoreline between 2018 and 2023.\n\n### Key findings\n- ~18.7 ha of shoreline retreat\n- Highest change in sectors A and B\n- Built-up expansion along the eastern edge\n\n> Confidence: 0.87 • Area: 18.7 ha • Sensor: Sentinel-2 L2A",
      },
    },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n```chart\n{\"type\":\"bar\",\"title\":\"Change by sector (ha)\",\"data\":[{\"name\":\"Sector A\",\"value\":9.2},{\"name\":\"Sector B\",\"value\":6.1},{\"name\":\"Sector C\",\"value\":3.4}]}\n```",
      },
    },
    {
      event: "answer_delta",
      payload: {
        chunk: "\n\n| Area | Change | Confidence |\n|---|---:|---:|\n| Sector A | 9.2 ha | 89% |\n| Sector B | 6.1 ha | 82% |\n| Sector C | 3.4 ha | 76% |",
      },
    },
    { event: "answer_delta", payload: { chunk: "\n\n![Before / After — 2018 vs 2023](comparison:2018-2023)" } },
    { event: "answer_delta", payload: { chunk: "\n\n![Change mask overlay](map:change-mask)\n\n[View change area](#mock_bbox_001) [Open evidence](#evidence)" } },
    { event: "final_answer", payload: {} },
    { event: "query_completed", payload: {} },
  ];
}

function groundingEvents(query: string): ExecutionEvent[] {
  return [
    ...base(query),
    {
      event: "planner_done",
      payload: {
        goal: "Ground water body",
        capabilities: ["grounding"],
        llm: "qwen-3.5-9b",
        goals: ["grounding"],
        crop_target: null,
        coreference_resolved: "none",
        task_router_map: { grounding: "M2: Grounding (bbox + mask RLE)" },
      },
    },
    { event: "execution_started", payload: { gis: { operation: "no-crop", cropApplied: false } } },
    { event: "model_started", payload: { model: "GroundingDINO" } },
    { event: "model_done", payload: { model: "GroundingDINO", detections: 1, bbox_xyxy: [120, 45, 310, 210], bbox_normalized: [0.18, 0.09, 0.47, 0.42], mask_rle: null, confidence: 0.87, status: "OK", num_detections: 1 } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.87 } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_GROUNDING } },
    { event: "thinking_done" },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "Water body detected in the northern sector with high confidence.\n\n> Confidence: 0.87 • Source: GroundingDINO • BBox: [0.18, 0.09, 0.47, 0.42] • BBox xyxy: [120, 45, 310, 210]",
      },
    },
    { event: "answer_delta", payload: { chunk: "\n\n![Detected water body — northern AOI](image:water-body)\n\n[Water body · 87%](#mock_bbox_001) [Zoom to feature](#mock_bbox_001)" } },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n| Property | Value |\n|---|---|\n| Label | Water body |\n| BBox (normalized) | 0.18, 0.09, 0.47, 0.42 |\n| BBox xyxy | 120, 45, 310, 210 |\n| Confidence | 87% |\n| Source | GroundingDINO |\n| Status | OK |",
      },
    },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n```chart\n{\"type\":\"bar\",\"title\":\"Detection confidence\",\"data\":[{\"name\":\"Water\",\"value\":0.87},{\"name\":\"Background\",\"value\":0.13}]}\n```",
      },
    },
    { event: "final_answer", payload: {} },
    { event: "query_completed", payload: {} },
  ];
}

function fusionEvents(query: string): ExecutionEvent[] {
  return [
    ...base(query),
    {
      event: "planner_done",
      payload: {
        goal: "Fuse optical+SAR",
        capabilities: ["fusion", "grounding"],
        llm: "qwen-3.5-9b",
        goals: ["optical_sar_fusion"],
        crop_target: null,
        task_router_map: { optical_sar_fusion: "M4: Optical-SAR Fusion (CROMA)" },
      },
    },
    { event: "execution_started", payload: { gis: { operation: "co-register S1+S2", cropApplied: false } } },
    { event: "model_started", payload: { model: "CROMA Fusion" } },
    { event: "model_done", payload: { model: "CROMA Fusion", confidence: 0.88, status: "OK", per_modality_confidence: { optical: 0.82, sar: 0.75, fused: 0.88 }, class_map_rle: { "built-up": "RLE_STRING_HERE", water: "RLE_STRING_HERE" } } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.88 } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_FUSION } },
    { event: "thinking_done" },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "Optical **82%**, SAR **75%**, fused **88%**. Water and built-up are consistent across optical and SAR modalities.\n\n> Per-modality confidence — optical 0.82 · sar 0.75 · fused 0.88 • Status: OK",
      },
    },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n```chart\n{\"type\":\"fusion\",\"title\":\"Modality confidence\",\"data\":[{\"name\":\"Optical\",\"value\":0.82},{\"name\":\"SAR\",\"value\":0.75},{\"name\":\"Fused\",\"value\":0.88}]}\n```",
      },
    },
    { event: "answer_delta", payload: { chunk: "\n\n| Modality | Confidence |\n|---|---:|\n| Optical | 82% |\n| SAR | 75% |\n| Fused | 88% |" } },
    { event: "answer_delta", payload: { chunk: "\n\n![Optical vs SAR split view](comparison:optical-sar)\n\n> Confidence: 0.88 • Fusion: CROMA cross-attention • Class map RLE: built-up / water / other\n\n[Open comparison](comparison:optical-sar) [View evidence](#evidence)" } },
    { event: "final_answer", payload: {} },
    { event: "query_completed", payload: {} },
  ];
}

function vqaEvents(query: string): ExecutionEvent[] {
  return [
    ...base(query),
    {
      event: "planner_done",
      payload: {
        goal: "Describe land-cover",
        capabilities: ["vqa"],
        llm: "qwen-3.5-9b",
        goals: ["vqa"],
        crop_target: null,
        task_router_map: { vqa: "M1: RS-VQA (open/closed)" },
      },
    },
    { event: "execution_started", payload: { gis: { operation: "no-crop", cropApplied: false } } },
    { event: "model_started", payload: { model: "RS-VQA" } },
    { event: "model_done", payload: { model: "RS-VQA", status: "OK", answer_text: "The image shows a mix of agricultural fields in the center, a small settlement cluster to the east, and a forested patch along the western edge.", answer_type: "open", confidence: 0.84 } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.84 } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_VQA } },
    { event: "thinking_done" },
    { event: "answer_delta", payload: { chunk: "![Selected image — img_001](image:img_001)\n\n> Image: img_001 • Sentinel-2 • 10 m • Single-scene" } },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "The image shows a mix of agricultural fields in the center, a small settlement cluster to the east, and a forested patch along the western edge.\n\n> Confidence: 0.84 • Answer type: open • Image: img_001 • Status: OK",
      },
    },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n| Field | Value |\n|---|---|\n| Task | vqa |\n| Query | Describe the land-cover and major objects visible in this image. |\n| Answer | Agricultural fields (center), settlement (east), forest (west) |\n| Type | open |\n| Confidence | 84% |",
      },
    },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n```chart\n{\"type\":\"bar\",\"title\":\"Land-cover confidence\",\"data\":[{\"name\":\"Agriculture\",\"value\":0.84},{\"name\":\"Settlement\",\"value\":0.62},{\"name\":\"Forest\",\"value\":0.71}]}\n```",
      },
    },
    { event: "final_answer", payload: {} },
    { event: "query_completed", payload: {} },
  ];
}

function cropEvents(query: string): ExecutionEvent[] {
  return [
    ...base(query),
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
    { event: "model_done", payload: { model: "GroundingDINO", detections: 1, bbox_xyxy: [15, 10, 45, 30], bbox_xyxy_absolute: [135, 55, 165, 75], bbox_normalized: [0.21, 0.11, 0.26, 0.14], label: "building footprint", confidence: 0.89, status: "OK", mask_rle: null } },
    { event: "evidence_started" },
    { event: "evidence_done", payload: { confidence: 0.88, note: "Aggregated Turn1 water body (0.87) + Turn2 structure (0.89) → EvidenceGraph updated" } },
    { event: "composer_started", payload: { llm: "qwen-3.5-9b" } },
    { event: "thinking_delta", payload: { chunk: THINKING_CROP } },
    { event: "thinking_done" },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "Inside the northern water body identified earlier **[120, 45, 310, 210]**, the high-resolution crop reveals a small building footprint along the northern perimeter.\n\n> Cropped ROI: [120, 45, 310, 210] → tile 190×165 • Detected: building footprint • BBox (cropped tile): [15, 10, 45, 30] • Absolute: [135, 55, 165, 75] • Confidence: 0.89 • Status: OK",
      },
    },
    { event: "answer_delta", payload: { chunk: "\n\n![Cropped ROI — structure inside water body](image:structure-crop)\n\n[Structure · 89%](#mock_bbox_002) [Zoom to crop](#mock_bbox_002)" } },
    {
      event: "answer_delta",
      payload: {
        chunk:
          "\n\n| Property | Value |\n|---|---|\n| Label | building footprint |\n| BBox xyxy (crop tile) | 15, 10, 45, 30 |\n| BBox xyxy (absolute) | 135, 55, 165, 75 |\n| BBox normalized | 0.21, 0.11, 0.26, 0.14 |\n| Source | GroundingDINO (cropped) |\n| Confidence | 89% |",
      },
    },
    { event: "final_answer", payload: {} },
    { event: "query_completed", payload: {} },
  ];
}