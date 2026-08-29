/**
 * chartSpec — single source of truth for SATIQ chart generation.
 *
 * Mirrors orchestrator/helpers/chart_spec.py — keep schemas in sync.
 * Provides: Zod-like validation (no extra dep), normalization, builders,
 * and the prompt fragment consumed by the agentic composer.
 *
 * Skill: .agents/skills/apexcharts-skill/SKILL.md
 */

export type ChartType =
  | "bar"
  | "area"
  | "line"
  | "donut"
  | "pie"
  | "radialBar"
  | "heatmap";

export type ChartUnit = "ha" | "%" | "confidence" | "count" | "px" | string;

export interface ChartDatum {
  name: string;
  value: number;
  meta?: string;
}

export interface ChartSpec {
  type: ChartType;
  title: string;
  data: ChartDatum[];
  unit?: ChartUnit;
  subtitle?: string;
  note?: string;
  yMin?: number;
  yMax?: number;
  colors?: string[];
}

// ── Constants ────────────────────────────────────────────────────────────

export const CHART_TYPES: readonly ChartType[] = [
  "bar",
  "area",
  "line",
  "donut",
  "pie",
  "radialBar",
  "heatmap",
] as const;

export const SATIQ_PALETTE = [
  "#06B6D4", // cyan
  "#22C55E", // green
  "#F59E0B", // amber
  "#64748B", // slate
  "#38bdf8", // sky
  "#8B5CF6", // violet
  "#EF4444", // red (rare)
  "#14B8A6", // teal
] as const;

export const CHART_LIMITS = {
  minData: 1,
  maxData: 12,
  displayMax: 8, // shown; remainder aggregated as "Other"
  maxTitleLen: 64,
  maxNameLen: 32,
  maxJsonBytes: 4096,
} as const;

// ── Validation ───────────────────────────────────────────────────────────

export interface ChartValidationError {
  field: string;
  message: string;
}

export function validateChartSpec(raw: unknown): {
  valid: boolean;
  spec?: ChartSpec;
  errors: ChartValidationError[];
} {
  const errors: ChartValidationError[] = [];

  if (!raw || typeof raw !== "object") {
    return { valid: false, errors: [{ field: "root", message: "Chart spec must be an object" }] };
  }
  const obj = raw as Record<string, unknown>;

  // type
  const type = obj.type;
  if (typeof type !== "string" || !(CHART_TYPES as readonly string[]).includes(type as string)) {
    errors.push({ field: "type", message: `type must be one of: ${CHART_TYPES.join(", ")}` });
  }

  // title
  if (typeof obj.title !== "string" || obj.title.trim().length === 0) {
    errors.push({ field: "title", message: "title is required (3-64 chars)" });
  } else if (obj.title.length > CHART_LIMITS.maxTitleLen) {
    errors.push({ field: "title", message: `title exceeds ${CHART_LIMITS.maxTitleLen} chars` });
  }

  // data
  if (!Array.isArray(obj.data)) {
    errors.push({ field: "data", message: "data must be an array of {name, value}" });
  } else {
    if (obj.data.length < CHART_LIMITS.minData) errors.push({ field: "data", message: "data must have at least 1 entry" });
    if (obj.data.length > CHART_LIMITS.maxData) errors.push({ field: "data", message: `data exceeds ${CHART_LIMITS.maxData} entries (truncate to ${CHART_LIMITS.displayMax})` });
    for (let i = 0; i < (obj.data as unknown[]).length; i++) {
      const d = (obj.data as Record<string, unknown>[])[i];
      if (!d || typeof d !== "object") {
        errors.push({ field: `data[${i}]`, message: "entry must be {name, value}" });
        continue;
      }
      if (typeof d.name !== "string" || d.name.trim().length === 0) {
        errors.push({ field: `data[${i}].name`, message: "name required, 1-32 chars" });
      } else if ((d.name as string).length > CHART_LIMITS.maxNameLen) {
        errors.push({ field: `data[${i}].name`, message: `name exceeds ${CHART_LIMITS.maxNameLen} chars` });
      }
      if (typeof d.value !== "number" || !isFinite(d.value)) {
        errors.push({ field: `data[${i}].value`, message: "value must be finite number" });
      }
    }
  }

  // note / subtitle length (soft)
  if (obj.note !== undefined && typeof obj.note !== "string") errors.push({ field: "note", message: "note must be string" });
  if (obj.subtitle !== undefined && typeof obj.subtitle !== "string") errors.push({ field: "subtitle", message: "subtitle must be string" });

  // JSON byte budget
  try {
    const len = JSON.stringify(obj).length;
    if (len > CHART_LIMITS.maxJsonBytes) errors.push({ field: "data", message: `JSON exceeds ${CHART_LIMITS.maxJsonBytes} bytes (${len})` });
  } catch {
    // ignore
  }

  if (errors.length > 0) return { valid: false, errors };

  return { valid: true, spec: obj as unknown as ChartSpec, errors: [] };
}

export function normalizeChartSpec(spec: ChartSpec): ChartSpec {
  const out: ChartSpec = { ...spec };

  // Unknown type → bar (most auditable)
  if (!((CHART_TYPES as readonly string[]).includes(out.type as string))) {
    out.type = "bar";
  }
  // pie → donut for consistency
  if (out.type === "pie") out.type = "donut";

  // Title fallback
  if (!out.title || out.title.trim().length === 0) out.title = "Analysis";

  // Truncate data to displayMax, aggregate remainder as "Other"
  if (out.data.length > CHART_LIMITS.displayMax) {
    const top = out.data.slice(0, CHART_LIMITS.displayMax - 1);
    const rest = out.data.slice(CHART_LIMITS.displayMax - 1);
    const otherValue = rest.reduce((s, d) => s + d.value, 0);
    // For confidence/% use mean, for ha use sum — heuristic: values ≤2 are confidence
    const isHa = rest.some((d) => d.value > 2);
    const aggregated = isHa ? otherValue : otherValue / rest.length;
    out.data = [...top, { name: "Other", value: Number(aggregated.toFixed(2)), meta: `${rest.length} more` }];
    if (!out.note) out.note = `Top ${CHART_LIMITS.displayMax} of ${spec.data.length} shown`;
    else out.note += ` · Top ${CHART_LIMITS.displayMax} of ${spec.data.length}`;
  }

  // Clamp name lengths
  out.data = out.data.map((d) => ({
    ...d,
    name: d.name.length > CHART_LIMITS.maxNameLen ? d.name.slice(0, CHART_LIMITS.maxNameLen - 1) + "…" : d.name,
  }));

  return out;
}

// ── Scale detection ──────────────────────────────────────────────────────

/** Heuristic: any value >2 → hectares; otherwise confidence/% (0-1 or 0-100). */
export function isHaScale(values: number[]): boolean {
  return values.some((v) => v > 2);
}

export function toDisplayValues(values: number[]): number[] {
  if (isHaScale(values)) return values;
  // confidence 0-1 → %
  return values.map((v) => Number((v * 100).toFixed(1)));
}

export function formatValue(value: number, unit?: ChartUnit, isHa?: boolean): string {
  if (unit === "ha" || (isHa && !unit)) return `${value} ha`;
  if (unit === "%" || unit === "confidence") return `${Math.round(value * (value <= 1 ? 100 : 1))}%`;
  // auto: >2 => ha, else %
  if (value > 2) return `${value} ha`;
  if (value <= 1) return `${Math.round(value * 100)}%`;
  return `${value}`;
}

// ── Builders (for mocks, tests, and agentic pipeline helpers) ───────────

export function buildChangeBySectorChart(
  sectors: Array<{ name: string; value: number }>,
  note = "Sentinel-2 • EPSG:32617 • 10 m GSD"
): ChartSpec {
  return normalizeChartSpec({ type: "bar", title: "Change by sector (ha)", data: sectors, unit: "ha", note });
}

export function buildConfidenceChart(
  title: string,
  data: ChartDatum[],
  note?: string
): ChartSpec {
  return normalizeChartSpec({ type: "bar", title, data, unit: "confidence", note });
}

export function buildFusionConfidenceChart(
  optical: number,
  sar: number,
  fused: number,
  type: ChartType = "bar"
): ChartSpec {
  return normalizeChartSpec({
    type,
    title: "Modality confidence",
    data: [
      { name: "Optical", value: optical },
      { name: "SAR", value: sar },
      { name: "Fused", value: fused },
    ],
    unit: "confidence",
    note: "CROMA cross-attention • per-modality confidence",
  });
}

export function buildLandCoverChart(
  entries: Array<{ name: string; value: number }>
): ChartSpec {
  return normalizeChartSpec({ type: "donut", title: "Land-cover confidence", data: entries, unit: "%", note: "RS-VQA" });
}

export function chartToFencedBlock(spec: ChartSpec): string {
  return "```chart\n" + JSON.stringify(spec) + "\n```";
}

export function parseChartBlock(raw: string): { spec: ChartSpec | null; errors: ChartValidationError[] } {
  const text = raw.trim();
  // strip ```chart / ``` fences if present
  const jsonText = text
    .replace(/^```chart\s*/i, "")
    .replace(/^```\s*/i, "")
    .replace(/\s*```\s*$/i, "")
    .trim();
  try {
    const parsed = JSON.parse(jsonText);
    const v = validateChartSpec(parsed);
    if (!v.valid) return { spec: null, errors: v.errors };
    return { spec: normalizeChartSpec(v.spec!), errors: [] };
  } catch (e) {
    return { spec: null, errors: [{ field: "json", message: `Invalid JSON: ${String(e)}` }] };
  }
}

// ── Prompt fragment (single source for orchestrator composer) ────────────

export const CHART_PROMPT_FRAGMENT = `CHART RULES — if your answer contains numbers, emit ONE \`\`\`chart block after the narrative, before the table:
- Type: bar (default) / donut for 2-4 proportional slices / area|line for temporal / radialBar for single gauge.
- Title: short, human, with unit. Example: "Change by sector (ha)".
- Data: [{name, value}] where value is ha (>2) OR confidence/percentage (0-1 or 0-100 normalized). Max 8 entries.
- JSON must be valid, no trailing commas, no comments. Keep under 4KB.
- Put provenance (sensor, CRS EPSG:32617, GSD 10 m) into "note", not into name.
- If no numbers, omit the chart block entirely — do not fabricate.

Examples:
\`\`\`chart
{"type":"bar","title":"Change by sector (ha)","data":[{"name":"Sector A","value":9.2},{"name":"Sector B","value":6.1},{"name":"Sector C","value":3.4}],"unit":"ha","note":"Sentinel-2 • EPSG:32617 • 10 m GSD"}
\`\`\`
\`\`\`chart
{"type":"donut","title":"Land-cover confidence","data":[{"name":"Agriculture","value":0.84},{"name":"Settlement","value":0.62},{"name":"Forest","value":0.71}],"unit":"%","note":"RS-VQA • img_001"}
\`\`\`
`;
