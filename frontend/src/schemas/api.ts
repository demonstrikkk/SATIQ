import { z } from "zod";

export const SpatialReferenceSchema = z.object({
  id: z.string(),
  type: z.enum(["bbox","polygon","mask","feature","image","date","modality","analysis"]),
  label: z.string(),
  confidence: z.number().optional(),
  source: z.string().optional(),
  imageId: z.string().optional(),
  bbox: z.tuple([z.number(), z.number(), z.number(), z.number()]).optional(),
  geometry: z.any().optional(),
});
export type SpatialReference = z.infer<typeof SpatialReferenceSchema>;

export const QueryRequestSchema = z.object({
  session_id: z.string(),
  query: z.string().min(1),
  image_refs: z.array(z.string()).optional(),
  spatial_refs: z.array(z.string()).optional(),
});
export type QueryRequest = z.infer<typeof QueryRequestSchema>;

export const AssetSchema = z.object({
  id: z.string(),
  filename: z.string(),
  crs: z.string(),
  resolution: z.number(),
  bands: z.array(z.string()),
  acquired: z.string(),
  platform: z.string(),
  product: z.string().optional(),
  cloud_cover: z.number().optional(),
});
export type Asset = z.infer<typeof AssetSchema>;
