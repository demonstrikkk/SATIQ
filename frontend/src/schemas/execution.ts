import { z } from "zod";

export const ExecutionStatusSchema = z.enum(["idle","queued","planning","executing","aggregating","composing","completed","failed","cancelled"]);
export type ExecutionStatus = z.infer<typeof ExecutionStatusSchema>;

export const ModelExecutionStateSchema = z.enum(["pending","running","completed","failed","skipped"]);
export type ModelExecutionState = z.infer<typeof ModelExecutionStateSchema>;

export const ExecutionEventSchema = z.object({
  event: z.enum([
    "query_started","input_started","input_done",
    "planner_started","planner_done","execution_started",
    "model_started","model_progress","model_done","evidence_started","evidence_done",
    "composer_started","thinking_delta","thinking_done","answer_delta","final_answer","query_completed","error","cancelled","queue_position"
  ]),
  payload: z.any().optional(),
  timestamp: z.number().optional(),
});
export type ExecutionEvent = z.infer<typeof ExecutionEventSchema>;

export const PlannerPayloadSchema = z.object({
  goal: z.string(),
  capabilities: z.array(z.string()),
  spatial_target: z.string().optional(),
  modalities: z.array(z.string()).optional(),
});
