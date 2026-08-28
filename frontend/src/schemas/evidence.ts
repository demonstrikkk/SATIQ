import { z } from "zod";

export const EvidenceNodeSchema = z.object({
  id: z.string(),
  type: z.enum(["vqa","grounding","change","fusion","geospatial"]),
  label: z.string(),
  confidence: z.number(),
  source: z.string(),
  turn: z.number().optional(),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]).optional(),
  meta: z.record(z.string(), z.any()).optional(),
});
export type EvidenceNode = z.infer<typeof EvidenceNodeSchema>;

export const EvidenceGraphSchema = z.object({
  query: z.string(),
  planner: z.object({ goal: z.string(), capabilities: z.array(z.string()) }),
  nodes: z.array(EvidenceNodeSchema),
  edges: z.array(z.object({ from: z.string(), to: z.string() })),
  finalConfidence: z.number().optional(),
});
export type EvidenceGraph = z.infer<typeof EvidenceGraphSchema>;
