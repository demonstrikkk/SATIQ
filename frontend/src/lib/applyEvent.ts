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
    if (p?.bbox_xyxy_absolute && p?.bbox_normalized) {
      useSessionStore.getState().addBbox({ id: `bbox_${Date.now()}`, label: p.label ?? "building footprint", bbox_xyxy: p.bbox_xyxy_absolute, bbox_normalized: p.bbox_normalized, confidence: p.confidence ?? 0.89, turn: 2 });
    }
    if (p?.model === "GroundingDINO" && !p?.bbox_xyxy_absolute && p?.bbox_normalized) {
      const bid = `bbox_${Date.now()}`;
      useMapStore.getState().addFeature({ id: bid, label: p.label ?? "Water body", confidence: p.confidence ?? 0.87, source: "GroundingDINO", bboxNorm: p.bbox_normalized, type: "bbox" } as any);
      useMapStore.getState().setSelectedFeatureId(bid);
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
    addMessage({ id, role: "assistant", content: "", streaming: true, thinking: "", thinkingStreaming: true, thinkingCollapsed: false, model: (ev.payload as any)?.llm });
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
    const code = (ev.payload as any)?.code ?? "";
    const raw = (ev.payload as any)?.message ?? "Analysis failed";
    let msg = raw;
    // MODEL_NOT_LINKED dedicated banner (GAP-6) — keeps generic path for other errors
    if (code === "MODEL_NOT_LINKED" || raw.includes("MODEL_NOT_LINKED") || raw.includes("MODEL_LOAD_ERROR")) {
      msg = `⚠️ **Models not linked** — checkpoints absent at \`models/model{1..4}/\`\n\nRun:\n\`\`\`bash\npython scripts/download_weights.py --model all\n# or set HF_TOKEN for gated models\n\`\`\`\nThen: \`docker compose up --build\`\n\nSee \`docs/FRIEND_HANDOFF.md#weights\` for exact paths. Preflight: \`powershell -File scripts/preflight.ps1\` must show \`present\` for all 4.`;
    } else if (code === "queue_full" || raw.includes("queue_full") || raw.includes("VRAM_QUEUE_FULL")) {
      msg = `⏳ **GPU busy — queue full** (VRAM_SEMAPHORE 2, max queue 4). Retry in ~6s.\n\nTip: wait for current job or use \`GET /api/v1/metrics\` to see \`vram.queue_depth\`.`;
    }
    if (lastAssistantId) {
      appendChunk(lastAssistantId, `\n\n> ${msg}`);
      setStreaming(lastAssistantId, false);
      setThinkingStreaming(lastAssistantId, false);
      setThinkingCollapsed(lastAssistantId, true);
    }
    setComposerStatus("failed" as any);
    setGlobalStatus("failed" as any);
  }
  if (ev.event === "queue_position") {
    const pos = (ev.payload as any)?.position ?? "?";
    const wait = (ev.payload as any)?.estimated_wait_ms ?? 6000;
    if (lastAssistantId) appendThinking(lastAssistantId, `⏳ GPU queue position ${pos} — est. wait ${wait}ms\n`);
  }
  if (ev.event === "cancelled") {
    if (lastAssistantId) {
      setStreaming(lastAssistantId, false);
      setThinkingStreaming(lastAssistantId, false);
      setThinkingCollapsed(lastAssistantId, true);
    }
    setComposerStatus("cancelled" as any);
    setGlobalStatus("cancelled" as any);
  }
}

export function resetLastAssistantId() { lastAssistantId = null; }
