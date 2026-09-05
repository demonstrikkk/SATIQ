/**
 * SATIQ shared contracts — single source of truth for the frontend ↔ gateway API.
 * Imported by both `frontend/` and `gateway/`. Keep schema changes here first.
 */

// ---------------------------------------------------------------------------
// Execution events (SSE payloads)
// ---------------------------------------------------------------------------

export type ExecutionEventName =
  | "query_started"
  | "input_started"
  | "input_done"
  | "planner_started"
  | "planner_done"
  | "execution_started"
  | "model_started"
  | "model_progress"
  | "model_done"
  | "evidence_started"
  | "evidence_done"
  | "composer_started"
  | "thinking_delta"
  | "thinking_done"
  | "answer_delta"
  | "final_answer"
  | "query_completed"
  | "error"
  | "cancelled";

export interface ExecutionEvent {
  event: ExecutionEventName;
  payload?: Record<string, unknown>;
  timestamp?: number;
}

// ---------------------------------------------------------------------------
// Query / execution
// ---------------------------------------------------------------------------

export interface AnalysisRequest {
  query: string;
  session_id?: string;
  asset_ids?: string[];
  spatial_refs?: string[];
  /** Forwarded Authorization header for orchestrator (gateway injects req.headers.authorization) */
  _authHeader?: string;
}

export interface AnalysisExecution {
  execution_id: string;
  session_id?: string;
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  created_at: string;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  message: string;
  token: string;
  user: { userId: string; username: string };
}

// ---------------------------------------------------------------------------
// Assets (uploads)
// ---------------------------------------------------------------------------

export interface AssetMeta {
  asset_id: string;
  filename: string;
  originalname: string;
  mime_type: string;
  size: number;
  url: string;
  uploaded_at: string;
  // Enriched by orchestrator ingest — optional, forwarded to pipeline
  width?: number;
  height?: number;
  crs?: string;
  gsd?: number;
  bands?: number;
  dtype?: string;
  geotiff_path?: string;
  thumbnail_preview?: string;
  orchestrator_validation?: unknown;
}

// ---------------------------------------------------------------------------
// Sessions
// ---------------------------------------------------------------------------

export interface SessionRecord {
  sessionId: string;
  userId: string;
  name: string;
  createdAt: string;
  updatedAt: string;
  metadata?: Record<string, unknown>;
  chatHistory?: unknown[];
}