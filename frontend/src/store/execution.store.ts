import { create } from "zustand";
import type { ExecutionStatus, ModelExecutionState } from "@/schemas/execution";

// Single source per spec — 7 adaptive steps (LLM planner → GIS → Router → Models → Locating → Evidence → Composer)
export type PipelineStepId = 'understanding' | 'preparing' | 'selecting' | 'analyzing' | 'locating' | 'validating' | 'generating';
export type PipelineStepStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface PipelineStep {
  id: PipelineStepId;
  status: PipelineStepStatus;
  title: string;
  subtitle?: string;
  durationMs?: number;
}

const INITIAL_PIPELINE: PipelineStep[] = [
  { id: 'understanding', status: 'pending', title: 'Understanding request', subtitle: 'LLM planner • intent + context' },
  { id: 'preparing', status: 'pending', title: 'Preparing spatial context', subtitle: 'GIS • raster • AOI • reprojection' },
  { id: 'selecting', status: 'pending', title: 'Selecting analysis tools', subtitle: 'Task router • model selection' },
  { id: 'analyzing', status: 'pending', title: 'Analyzing imagery', subtitle: 'Running specialized model(s)' },
  { id: 'locating', status: 'pending', title: 'Locating spatial evidence', subtitle: 'Grounding • masks • boxes' },
  { id: 'validating', status: 'pending', title: 'Validating evidence', subtitle: 'Evidence engine • confidence' },
  { id: 'generating', status: 'pending', title: 'Generating response', subtitle: 'LLM composer • grounded answer' },
];

interface ExecutionState {
  globalStatus: ExecutionStatus;
  plannerStatus: ModelExecutionState;
  modelStatus: ModelExecutionState;
  evidenceStatus: ModelExecutionState;
  composerStatus: ModelExecutionState;
  // new: input handler status for pipeline step 1
  inputStatus: PipelineStepStatus;
  // single source of truth pipeline
  pipelineSteps: PipelineStep[];
  hasReceivedFirstProgress: boolean;

  plannerDetails?: {
    goal: string;
    capabilities: string[];
    spatial_target?: string;
    llm?: string;
    goals?: string[];
    crop_target?: [number, number, number, number] | null;
    coreference_resolved?: string;
    task_router_map?: Record<string, string>;
  };
  modelDetails?: { activeModels: string[] };
  gisDetails?: { operation: string; cropApplied: boolean; roi?: string };
  taskRouter?: Record<string, string>;
  spatialSnapshot?: { lastCrop: [number, number, number, number] | null; bboxCount: number };

  setGlobalStatus: (s: ExecutionStatus) => void;
  setPlannerStatus: (s: ModelExecutionState, d?: any) => void;
  setModelStatus: (s: ModelExecutionState, d?: any) => void;
  setEvidenceStatus: (s: ModelExecutionState, d?: any) => void;
  setComposerStatus: (s: ModelExecutionState, d?: any) => void;
  setInputStatus: (s: PipelineStepStatus, d?: any) => void;
  setGisDetails: (d: ExecutionState["gisDetails"]) => void;
  setTaskRouter: (m: Record<string, string>) => void;
  setPipelineStep: (id: PipelineStepId, status: PipelineStepStatus, patch?: Partial<PipelineStep>) => void;
  reset: () => void;
}

export const useExecutionStore = create<ExecutionState>((set) => ({
  globalStatus: "idle",
  plannerStatus: "pending",
  modelStatus: "pending",
  evidenceStatus: "pending",
  composerStatus: "pending",
  inputStatus: "pending",
  pipelineSteps: INITIAL_PIPELINE,
  hasReceivedFirstProgress: false,

  setGlobalStatus: (globalStatus) => set((s) => {
    // keep understanding in sync with global queued/planning
    let steps = s.pipelineSteps;
    if (globalStatus === "queued" || globalStatus === "planning") {
      steps = steps.map((st) => (st.id === "understanding" && st.status === "pending" ? { ...st, status: "running" as PipelineStepStatus } : st));
    }
    return { globalStatus, pipelineSteps: steps };
  }),
  setPlannerStatus: (plannerStatus, details) =>
    set((s) => {
      const durationMs = details?.durationMs;
      const mapped = (plannerStatus === "running" ? "running" : plannerStatus === "completed" ? "completed" : plannerStatus === "failed" ? "failed" : "pending") as PipelineStepStatus;
      const newSteps = s.pipelineSteps.map((step) => {
        if (step.id === "understanding" || step.id === "selecting") {
          return { ...step, status: mapped, subtitle: details?.goal ? `${details.goal} • ${details.capabilities?.join(", ") ?? step.subtitle}` : step.subtitle, ...(durationMs !== undefined && step.id === "selecting" ? { durationMs } : {}) };
        }
        return step;
      });
      return { plannerStatus, plannerDetails: details ?? s.plannerDetails, pipelineSteps: newSteps, hasReceivedFirstProgress: true };
    }),
  setModelStatus: (modelStatus, details) =>
    set((s) => {
      const durationMs = details?.durationMs;
      const mapped = (modelStatus === "running" ? "running" : modelStatus === "completed" ? "completed" : modelStatus === "failed" ? "failed" : "pending") as PipelineStepStatus;
      const newSteps = s.pipelineSteps.map((step) => {
        if (step.id === "analyzing" || step.id === "locating") {
          return { ...step, status: mapped, subtitle: details?.activeModels?.join(", ") ?? step.subtitle, ...(durationMs !== undefined && step.id === "locating" ? { durationMs } : {}) };
        }
        return step;
      });
      return { modelStatus, modelDetails: details ?? s.modelDetails, pipelineSteps: newSteps, hasReceivedFirstProgress: true };
    }),
  setEvidenceStatus: (evidenceStatus, details?: any) =>
    set((s) => {
      const durationMs = details?.durationMs;
      const mapped = (evidenceStatus === "running" ? "running" : evidenceStatus === "completed" ? "completed" : evidenceStatus === "failed" ? "failed" : "pending") as PipelineStepStatus;
      const newSteps = s.pipelineSteps.map((step) => (step.id === "validating" ? { ...step, status: mapped, ...(durationMs !== undefined ? { durationMs } : {}) } : step));
      return { evidenceStatus, pipelineSteps: newSteps, hasReceivedFirstProgress: true };
    }),
  setComposerStatus: (composerStatus, details?: any) =>
    set((s) => {
      const durationMs = details?.durationMs;
      const mapped = (composerStatus === "running" ? "running" : composerStatus === "completed" ? "completed" : composerStatus === "failed" ? "failed" : "pending") as PipelineStepStatus;
      const newSteps = s.pipelineSteps.map((step) => (step.id === "generating" ? { ...step, status: mapped, ...(durationMs !== undefined ? { durationMs } : {}) } : step));
      return { composerStatus, pipelineSteps: newSteps, hasReceivedFirstProgress: true };
    }),
  setInputStatus: (inputStatus, details?: any) =>
    set((s) => {
      const durationMs = details?.durationMs;
      const newSteps = s.pipelineSteps.map((step) => (step.id === "preparing" ? { ...step, status: inputStatus, ...(durationMs !== undefined ? { durationMs } : {}) } : step));
      return { inputStatus, pipelineSteps: newSteps, hasReceivedFirstProgress: true };
    }),
  setGisDetails: (gisDetails) => set({ gisDetails }),
  setTaskRouter: (taskRouter) => set({ taskRouter }),
  setPipelineStep: (id, status, patch) => set((s) => ({
    pipelineSteps: s.pipelineSteps.map(step => step.id === id ? { ...step, status, ...patch } : step),
    hasReceivedFirstProgress: true,
  })),
  reset: () =>
    set({
      globalStatus: "idle",
      plannerStatus: "pending",
      modelStatus: "pending",
      evidenceStatus: "pending",
      composerStatus: "pending",
      inputStatus: "pending",
      pipelineSteps: INITIAL_PIPELINE,
      hasReceivedFirstProgress: false,
      plannerDetails: undefined,
      modelDetails: undefined,
      gisDetails: undefined,
      taskRouter: undefined,
      spatialSnapshot: undefined,
    }),
}));
