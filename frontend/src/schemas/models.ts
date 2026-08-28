import { z } from "zod";

// Shared production fields per review
const BaseStatus = z.object({
  status: z.enum(["OK", "FAILED"]).default("OK"),
  error_message: z.string().nullable().default(null),
});

// Model 1: RS-VQA — Qwen 3.5 9B is planner/composer, but VQA is specialist perception
export const VqaOutputSchema = BaseStatus.extend({
  task: z.literal("vqa"),
  query: z.string(),
  image_id: z.string(),
  answer_text: z.string(),
  answer_type: z.enum(["open", "closed"]),
  answer_short: z.string().nullable(),
  confidence: z.number().min(0).max(1),
});
export type VqaOutput = z.infer<typeof VqaOutputSchema>;

// Model 2: Grounding — bbox in pixel + normalized, optional SAM mask
export const GroundingDetectionSchema = z.object({
  label: z.string(),
  bbox_xyxy: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  bbox_normalized: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  mask_rle: z.string().nullable(),
  confidence: z.number().min(0).max(1),
});
export const GroundingOutputSchema = BaseStatus.extend({
  task: z.literal("grounding"),
  query: z.string(),
  image_id: z.string(),
  detections: z.array(GroundingDetectionSchema),
  num_detections: z.number().int().min(0),
});
export type GroundingOutput = z.infer<typeof GroundingOutputSchema>;

// Model 3: Change-VQA
export const ChangeVqaOutputSchema = BaseStatus.extend({
  task: z.literal("change_vqa"),
  query: z.string(),
  image_t1_id: z.string(),
  image_t2_id: z.string(),
  answer_text: z.string(),
  change_categories: z.array(z.string()),
  change_mask_rle: z.string().nullable(),
  confidence: z.number().min(0).max(1),
  units: z.string().default("hectares").optional(),
});
export type ChangeVqaOutput = z.infer<typeof ChangeVqaOutputSchema>;

// Model 4: Optical-SAR Fusion — CROMA
export const FusionOutputSchema = BaseStatus.extend({
  task: z.literal("optical_sar_fusion"),
  query: z.string(),
  optical_image_id: z.string(),
  sar_image_id: z.string(),
  answer_text: z.string(),
  class_map_rle: z.record(z.string(), z.string()),
  per_modality_confidence: z.object({
    optical: z.number().min(0).max(1),
    sar: z.number().min(0).max(1),
    fused: z.number().min(0).max(1),
  }),
  units: z.string().default("hectares").optional(),
});
export type FusionOutput = z.infer<typeof FusionOutputSchema>;

export const AnyModelOutputSchema = z.union([VqaOutputSchema, GroundingOutputSchema, ChangeVqaOutputSchema, FusionOutputSchema]);
export type AnyModelOutput = z.infer<typeof AnyModelOutputSchema>;

// Qwen 3.5 9B — LLM planner & composer (stateless perception is delegate)
export const QwenPlannerOutputSchema = z.object({
  model: z.literal("qwen-3.5-9b").default("qwen-3.5-9b"),
  goals: z.array(z.enum(["vqa", "grounding", "change_vqa", "optical_sar_fusion", "crop"])),
  crop_target: z.tuple([z.number(), z.number(), z.number(), z.number()]).nullable(), // bbox_xyxy or null
  coreference_resolved: z.string().optional(), // e.g. "that water body -> [120,45,310,210]"
  task_router_map: z.record(z.string(), z.string()).optional(), // goal -> model
});
export type QwenPlannerOutput = z.infer<typeof QwenPlannerOutputSchema>;
