import type { AnalysisRequest, ExecutionEvent } from "../../../../shared/contracts";

/**
 * AnalysisProvider — the pluggable boundary between the gateway and the
 * intelligence layer. The frontend never knows which provider is running.
 *
 * CURRENT:  MockAnalysisProvider (deterministic demo, behind ANALYSIS_PROVIDER=mock)
 * FUTURE:   AgenticAnalysisProvider (planner + model router + geo tools + VLM composer)
 *
 * Selection is driven by env `ANALYSIS_PROVIDER` (default: "mock").
 */
export interface AnalysisProvider {
  readonly name: string;
  execute(request: AnalysisRequest, signal: AbortSignal): AsyncGenerator<ExecutionEvent>;
}

export function selectProvider(env: NodeJS.ProcessEnv = process.env): AnalysisProvider {
  const kind = (env.ANALYSIS_PROVIDER ?? "agentic").toLowerCase();
  if (kind === "mock") {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { MockAnalysisProvider } = require("./mock-analysis.provider");
    return new MockAnalysisProvider();
  }
  if (kind === "agentic") {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { AgenticAnalysisProvider } = require("./agentic-analysis.provider");
    console.log("[analysis] Using AgenticAnalysisProvider →", env.ORCHESTRATOR_URL ?? "http://localhost:8000");
    return new AgenticAnalysisProvider();
  }
  throw new Error(`Unknown ANALYSIS_PROVIDER "${kind}". Valid values: mock, agentic.`);
}