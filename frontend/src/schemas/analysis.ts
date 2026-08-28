import { z } from "zod";

export const AnalysisCategorySchema = z.enum(["change","grounding","vqa","fusion","landcover","general"]);
export type AnalysisCategory = z.infer<typeof AnalysisCategorySchema>;

export const AnalysisSchema = z.object({
  id: z.string(),
  title: z.string(),
  category: AnalysisCategorySchema,
  createdAt: z.string(),
  status: z.enum(["draft","running","completed","failed"]),
  confidence: z.number().min(0).max(1).optional(),
  thumbnail: z.string().optional(),
});
export type Analysis = z.infer<typeof AnalysisSchema>;

export const AnalysisListSchema = z.array(AnalysisSchema);
