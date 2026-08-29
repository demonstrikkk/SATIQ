import { useExecutionStore } from "@/store/execution.store";
import { useChatStore } from "@/store/chat.store";
import { useMapStore } from "@/store/map.store";
import { useSessionStore } from "@/store/session.store";
import type { ExecutionEvent } from "@/schemas/execution";

let lastAssistantId: string | null = null;

export function applyExecutionEvent(ev: ExecutionEvent) {
  const { setGlobalStatus, setPlannerStatus, setModelStatus, setEvidenceStatus, setComposerStatus, setGisDetails, setTaskRouter, setInputStatus, reset } = useExecutionStore.getState();
  const { addMessage, appendChunk, setStreaming, appendThinking, setThinkingStreaming, setThinkingCollapsed } = useChatStore.getState();

  if (ev.event === "query_started") { reset(); setGlobalStatus("queued"); setInputStatus("pending"); lastAssistantId = null; }
  if (ev.event === "input_started") { setGlobalStatus("queued"); setInputStatus("running"); }
  if (ev.event === "input_done") { setInputStatus("completed", ev.payload); }
  if (ev.event === "planner_started") { setGlobalStatus("planning"); setPlannerStatus("running"); }
  if (ev.event === "planner_done") {
    setPlannerStatus("completed", ev.payload);
    if ((ev.payload as any)?.task_router_map) setTaskRouter((ev.payload as any).task_router_map);
    if ((ev.payload as any)?.crop_target) useSessionStore.getState().setLastCrop((ev.payload as any).crop_target);
  }
  if (ev.event === "execution_started") {
    setGlobalStatus("executing");
    setModelStatus("running", { activeModels: ["ChangeChat", "GroundingDINO"] });
    if ((ev.payload as any)?.gis) setGisDetails((ev.payload as any).gis);
  }
  if (ev.event === "model_started") { setModelStatus("running", { activeModels: [(ev.payload as any)?.model] }); }
  if (ev.event === "model_done") {
    setModelStatus("completed");
    const p: any = ev.payload;
    if (p?.bbox_xyxy && p?.bbox_normalized) {
      const bbox = p.bbox_xyxy as [number, number, number, number];
      const norm = p.bbox_normalized as [number, number, number, number];
      const label = p.label ?? "detection";
      const turn = useChatStore.getState().messages.filter(m => m.role === "user").length;
      useSessionStore.getState().addBbox({ id: `bbox_${Date.now()}`, label, bbox_xyxy: bbox, bbox_normalized: norm, confidence: p.confidence ?? 0.87, turn });
      useSessionStore.getState().addTurn({ id: `turn_${turn}`, turn, query: label, bbox_xyxy: bbox, bbox_normalized: norm, label, confidence: p.confidence });
    }
    if (p?.bbox_xyxy_absolute) {
      useSessionStore.getState().addBbox({ id: "mock_bbox_002", label: p.label ?? "building footprint", bbox_xyxy: [135,55,165,75], bbox_normalized: p.bbox_normalized ?? [0.21,0.11,0.26,0.14], confidence: p.confidence ?? 0.89, turn: 2 });
    }
    if (p?.model === "GroundingDINO" && !p?.bbox_xyxy_absolute) {
      useMapStore.getState().addFeature({ id: "mock_bbox_001", label: p.label ?? "Water body", confidence: p.confidence ?? 0.87, source: "GroundingDINO", bboxNorm: p.bbox_normalized ?? [0.18, 0.09, 0.47, 0.42], lngLat: [[-80.4, 31.45], [-80.35, 31.5]], type: "bbox" } as any);
      useMapStore.getState().setSelectedFeatureId("mock_bbox_001");
    }
    if (p?.model === "ChangeChat") {
      const s = useMapStore.getState();
      if (!(s.layers as any).changeMask) (s as any).toggleLayer?.("changeMask");
    }
  }
  if (ev.event === "evidence_started") { setGlobalStatus("aggregating"); setEvidenceStatus("running"); }
  if (ev.event === "evidence_done") { setEvidenceStatus("completed"); }
  if (ev.event === "composer_started") {
    setGlobalStatus("composing"); setComposerStatus("running");
    const id = `ans_${Date.now()}`;
    lastAssistantId = id;
    addMessage({ id, role: "assistant", content: "", streaming: true, thinking: "", thinkingStreaming: true, thinkingCollapsed: false });
  }
  if (ev.event === "thinking_delta") {
    if (lastAssistantId) appendThinking(lastAssistantId, (ev.payload as any)?.chunk ?? "");
  }
  if (ev.event === "thinking_done") {
    if (lastAssistantId) {
      setThinkingStreaming(lastAssistantId, false);
      setTimeout(() => lastAssistantId && setThinkingCollapsed(lastAssistantId, true), 800);
    }
  }
  if (ev.event === "answer_delta") {
    if (lastAssistantId) appendChunk(lastAssistantId, (ev.payload as any)?.chunk ?? "");
  }
  if (ev.event === "final_answer") {
    if (lastAssistantId) setStreaming(lastAssistantId, false);
    setComposerStatus("completed");
  }
  if (ev.event === "query_completed") { setGlobalStatus("completed"); }
  if (ev.event === "error") {
    // surface as assistant message if no final_answer
    const msg = (ev.payload as any)?.message ?? "Analysis failed";
    if (lastAssistantId) {
      appendChunk(lastAssistantId, `\n\n> ⚠️ ${msg}`);
      setStreaming(lastAssistantId, false);
    }
    setComposerStatus("failed" as any);
    setGlobalStatus("failed" as any);
  }
  if (ev.event === "cancelled") { setGlobalStatus("cancelled" as any); }
}

export function resetLastAssistantId() { lastAssistantId = null; }
