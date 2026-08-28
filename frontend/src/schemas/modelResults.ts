import { z } from "zod";

export const BaseModelResultSchema = z.object({
  task: z.string(),
  status: z.enum(["OK","FAILED"]),
  error_message: z.string().nullable().optional(),
  confidence: z.number(),
});
export type BaseModelResult = z.infer<typeof BaseModelResultSchema>;

export const DetectionSchema = z.object({
  label: z.string(),
  bbox_xyxy: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  bbox_normalized: z.tuple([z.number(), z.number(), z.number(), z.number()]),
  mask_rle: z.string().nullable().optional(),
  confidence: z.number(),
});
export type Detection = z.infer<typeof DetectionSchema>;

export const GroundingResultSchema = BaseModelResultSchema.extend({
  task: z.literal("grounding"),
  query: z.string(),
  image_id: z.string(),
  detections: z.array(DetectionSchema),
  num_detections: z.number(),
});
export type GroundingResult = z.infer<typeof GroundingResultSchema>;

export const VQAResultSchema = BaseModelResultSchema.extend({
  task: z.literal("vqa"),
  question: z.string(),
  answer: z.string(),
});
export type VQAResult = z.infer<typeof VQAResultSchema>;

export const ChangeResultSchema = BaseModelResultSchema.extend({
  task: z.literal("change_vqa"),
  description: z.string(),
  area_ha: z.number().optional(),
  mask_available: z.boolean().optional(),
});
export type ChangeResult = z.infer<typeof ChangeResultSchema>;

export const FusionResultSchema = BaseModelResultSchema.extend({
  task: z.literal("fusion"),
  optical_confidence: z.number(),
  sar_confidence: z.number(),
  fused_confidence: z.number(),
  summary: z.string(),
});
export type FusionResult = z.infer<typeof FusionResultSchema>;
