import { useExecutionStore } from "@/store/execution.store";
import { useChatStore } from "@/store/chat.store";
import { useMapStore } from "@/store/map.store";
import { useSessionStore } from "@/store/session.store";
import type { ExecutionEvent } from "@/schemas/execution";
import { coastalChangeEvents, groundingEvents, fusionEvents, vqaEvents, groundingCropSecondEvents } from "./executionEvents";

// ── cancellable controller (mock mode) ───────────────────────────────
let activeController: AbortController | null = null;

export function isMockGenerating(): boolean {
  return activeController !== null && !activeController.signal.aborted;
}
export function cancelCurrentQuery(): boolean {
  if (!activeController || activeController.signal.aborted) return false;
  activeController.abort();
  // finalize UI: stop streaming flags, move execution to cancelled
  try {
    const lastId = (emitSequence as any)._lastId as string | undefined;
    if (lastId) {
      const { setStreaming, setThinkingStreaming } = useChatStore.getState();
      setStreaming(lastId, false);
      setThinkingStreaming(lastId, false);
    }
    const { setGlobalStatus, setComposerStatus } = useExecutionStore.getState();
    setComposerStatus("failed" as any);
    setGlobalStatus("cancelled" as any);
  } catch {}
  return true;
}
function abortableSleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) return Promise.reject(new DOMException("Aborted","AbortError"));
  return new Promise<void>((resolve, reject)=>{
    const t = setTimeout(()=> { signal?.removeEventListener("abort", onAbort); resolve(); }, ms);
    const onAbort = ()=> { clearTimeout(t); reject(new DOMException("Aborted","AbortError")); };
    signal?.addEventListener("abort", onAbort, { once:true });
  });
}

async function emitSequence(events: ExecutionEvent[], onEvent: (e: ExecutionEvent) => void) {
  // create fresh controller for this run
  const controller = new AbortController();
  activeController = controller;
  const signal = controller.signal;

  const { setGlobalStatus, setPlannerStatus, setModelStatus, setEvidenceStatus, setComposerStatus, setGisDetails, setTaskRouter, setInputStatus, reset } = useExecutionStore.getState();
  const { addMessage, appendChunk, setStreaming, appendThinking, setThinkingStreaming, setThinkingCollapsed } = useChatStore.getState();

  try {
  for (const ev of events) {
    if (signal.aborted) break;
    onEvent(ev);
    if (ev.event === "query_started") { reset(); setGlobalStatus("queued"); setInputStatus("pending"); }
    if (ev.event === "input_started") { setGlobalStatus("queued"); setInputStatus("running"); }
    if (ev.event === "input_done") { setInputStatus("completed", ev.payload); }
    if (ev.event === "planner_started") { setGlobalStatus("planning"); setPlannerStatus("running"); }
    if (ev.event === "planner_done") {
      setPlannerStatus("completed", ev.payload);
      if (ev.payload?.task_router_map) setTaskRouter(ev.payload.task_router_map);
      if (ev.payload?.crop_target) useSessionStore.getState().setLastCrop(ev.payload.crop_target);
    }
    if (ev.event === "execution_started") {
      setGlobalStatus("executing");
      setModelStatus("running", { activeModels: ["ChangeChat", "GroundingDINO"] });
      if (ev.payload?.gis) setGisDetails(ev.payload.gis);
    }
    if (ev.event === "model_started") { setModelStatus("running", { activeModels: [ev.payload?.model] }); }
    if (ev.event === "model_done") {
      setModelStatus("completed");
      if (ev.payload?.bbox_xyxy && ev.payload?.bbox_normalized) {
        const bbox = ev.payload.bbox_xyxy as [number, number, number, number];
        const norm = ev.payload.bbox_normalized as [number, number, number, number];
        const label = ev.payload.label ?? "detection";
        const turn = useChatStore.getState().messages.filter(m => m.role === "user").length;
        useSessionStore.getState().addBbox({ id: `bbox_${Date.now()}`, label, bbox_xyxy: bbox, bbox_normalized: norm, confidence: ev.payload.confidence ?? 0.87, turn });
        useSessionStore.getState().addTurn({ id: `turn_${turn}`, turn, query: label, bbox_xyxy: bbox, bbox_normalized: norm, label, confidence: ev.payload.confidence });
      }
      if (ev.payload?.bbox_xyxy_absolute) {
        const abs = ev.payload.bbox_xyxy_absolute as [number, number, number, number];
        useSessionStore.getState().addBbox({ id: "mock_bbox_002", label: ev.payload.label ?? "building footprint", bbox_xyxy: [135,55,165,75], bbox_normalized: ev.payload.bbox_normalized ?? [0.21,0.11,0.26,0.14], confidence: ev.payload.confidence ?? 0.89, turn: 2 });
        useSessionStore.getState().addTurn({ id: `turn_2`, turn: 2, query: "structure inside water body", bbox_xyxy: abs as any, label: "building footprint", confidence: 0.89, crop_target: [120,45,310,210] });
      }
      if (ev.payload?.model === "GroundingDINO" && !ev.payload?.bbox_xyxy_absolute) {
        useMapStore.getState().addFeature({ id: "mock_bbox_001", label: ev.payload.label ?? "Water body", confidence: ev.payload.confidence ?? 0.87, source: "GroundingDINO", bboxNorm: ev.payload.bbox_normalized ?? [0.18, 0.09, 0.47, 0.42], lngLat: [[-80.4, 31.45], [-80.35, 31.5]], type: "bbox" });
        useMapStore.getState().setSelectedFeatureId("mock_bbox_001");
      }
      if (ev.payload?.label === "building footprint" || ev.payload?.bbox_xyxy_absolute) {
        useMapStore.getState().addFeature({ id: "mock_bbox_002", label: "Building footprint (inside water)", confidence: 0.89, source: "GroundingDINO (cropped)", bboxNorm: [0.21, 0.11, 0.26, 0.14], type: "bbox" });
        useMapStore.getState().setSelectedFeatureId("mock_bbox_002");
      }
      if (ev.payload?.model === "ChangeChat") {
        const s = useMapStore.getState();
        if (!s.layers.changeMask) s.toggleLayer("changeMask");
      }
    }
    if (ev.event === "evidence_started") { setGlobalStatus("aggregating"); setEvidenceStatus("running"); }
    if (ev.event === "evidence_done") { setEvidenceStatus("completed"); }
    if (ev.event === "composer_started") {
      setGlobalStatus("composing"); setComposerStatus("running");
      const id = `ans_${Date.now()}`;
      (emitSequence as any)._lastId = id;
      addMessage({ id, role: "assistant", content: "", streaming: true, thinking: "", thinkingStreaming: true, thinkingCollapsed: false });
    }
    if (ev.event === "thinking_delta") {
      const id = (emitSequence as any)._lastId;
      const chunk: string = ev.payload?.chunk ?? "";
      // stream thinking char by char for realism — abortable
      for (const ch of chunk) {
        if (signal.aborted) break;
        appendThinking(id, ch);
        try { await abortableSleep(8, signal); } catch { break; }
      }
      try { await abortableSleep(40, signal); } catch {}
    }
    if (ev.event === "thinking_done") {
      const id = (emitSequence as any)._lastId;
      setThinkingStreaming(id, false);
      // auto-collapse after 800ms per spec
      setTimeout(() => setThinkingCollapsed(id, true), 800);
    }
    if (ev.event === "answer_delta") {
      const id = (emitSequence as any)._lastId;
      const chunk: string = ev.payload?.chunk ?? "";
      const chartRe = /```chart[\s\S]*?```/g;
      const segments: string[] = [];
      let last = 0;
      let m: RegExpExecArray | null;
      while ((m = chartRe.exec(chunk)) !== null) {
        if (m.index > last) segments.push(chunk.slice(last, m.index));
        segments.push(m[0]);
        last = m.index + m[0].length;
      }
      if (last < chunk.length) segments.push(chunk.slice(last));
      if (segments.length === 1) {
        const lines = chunk.split("\n");
        for (let i = 0; i < lines.length; i++) {
          if (signal.aborted) break;
          const line = lines[i]! + (i < lines.length - 1 ? "\n" : "");
          if (line.trim().startsWith("```") || line.includes("|") || line.startsWith(">") || line.startsWith("![")) {
            appendChunk(id, line);
            try { await abortableSleep(90, signal);} catch{ break; }
          } else {
            for (const ch of line) {
              if (signal.aborted) break;
              appendChunk(id, ch);
              try { await abortableSleep(6, signal);} catch{ break; }
            }
            try { await abortableSleep(20, signal);} catch{}
          }
        }
      } else {
        for (const seg of segments) {
          if (signal.aborted) break;
          if (seg.startsWith("```chart")) {
            try { await abortableSleep(320, signal);} catch{ break; }
            appendChunk(id, seg);
            try { await abortableSleep(220, signal);} catch{}
          } else {
            const lines = seg.split("\n");
            for (let i = 0; i < lines.length; i++) {
              if (signal.aborted) break;
              const line = lines[i]! + (i < lines.length - 1 ? "\n" : "");
              if (line.includes("|") || line.startsWith(">") || line.startsWith("![")) {
                appendChunk(id, line);
                try { await abortableSleep(110, signal);} catch{ break; }
              } else {
                for (const ch of line) {
                  if (signal.aborted) break;
                  appendChunk(id, ch);
                  try { await abortableSleep(6, signal);} catch{ break; }
                }
                try { await abortableSleep(18, signal);} catch{}
              }
            }
          }
        }
      }
    }
    if (ev.event === "final_answer") {
      if (signal.aborted) break;
      const id = (emitSequence as any)._lastId;
      if (id) setStreaming(id, false);
      setComposerStatus("completed");
    }
    if (ev.event === "query_completed") { if (!signal.aborted) setGlobalStatus("completed"); }
    try { await abortableSleep(ev.event === "thinking_delta" ? 20 : ev.event === "answer_delta" ? 60 : 280, signal); } catch { break; }
  }
  } catch (e:any) {
    if (e?.name !== "AbortError") throw e;
  } finally {
    if (activeController === controller) activeController = null;
  }
}

export async function simulateAnalysisQuery(query: string, _ctxRefs: any[]) {
  const q = query.toLowerCase().trim();
  // Spec hint direct mapping — ensures 6 demo workflows hit correctly even before regex
  let hintEvents: ExecutionEvent[] | null = null;
  if (q === "what is visible in this image?".toLowerCase()) hintEvents = vqaEvents();
  else if (q === "find the water body in the north".toLowerCase()) hintEvents = groundingEvents();
  else if (q === "locate agricultural fields".toLowerCase()) hintEvents = groundingEvents();
  else if (q === "what changed between these dates?".toLowerCase()) hintEvents = coastalChangeEvents();
  else if (q === "show where built-up area increased".toLowerCase()) hintEvents = coastalChangeEvents();
  else if (q === "compare the optical and sar imagery".toLowerCase()) hintEvents = fusionEvents(query);
  // Helper to attach LLM-inspired follow-ups (chat-only, clickable)
  const attachFollowUps = (scenario: string) => {
    const lastId = (emitSequence as any)._lastId as string | undefined;
    if (!lastId) return;
    // LLM may or may not provide follow-ups — 18% chance no follow-ups
    if (Math.random() < 0.18) return;
    const map: Record<string, string[]> = {
      coastal: ["Break down change by sector", "What caused the retreat?", "Show built-up increase alone"],
      grounding: ["What is near this water body?", "Show confidence breakdown", "Find other water bodies"],
      fusion: ["Which modality was stronger?", "Show SAR texture alone", "Explain fusion confidence"],
      vqa: ["Count built-up clusters", "Describe vegetation health", "Where is the settlement?"],
      crop: ["Zoom to full water body", "What surrounds this structure?", "Estimate its area"],
    };
    const qs = map[scenario] ?? ["Tell me more", "Show on map", "Explain confidence"];
    try { useChatStore.getState().setFollowUpQuestions(lastId, qs.slice(0, 3)); } catch {}
  };

  if (hintEvents) {
    let events = hintEvents;
    const imgContexts = (_ctxRefs || []).filter((c: any) => c.type === "image" || c.type === "aoi" || c.preview);
    if (imgContexts.length > 0) {
      const imgBlocks = imgContexts
        .map((c: any) => {
          if (c.type === "aoi") return `> **AOI attached:** ${c.label} — will be used as spatial filter.\n\n`;
          const alt = c.label || c.fileName || "Attached image";
          // Use real preview (data: or blob: or http) if available, so the *actual uploaded pixels* appear in the chat.
          const src = c.preview && String(c.preview).length > 10 ? String(c.preview) : `image:${c.id || alt.replace(/\s+/g, "-").toLowerCase()}`;
          return `![${alt}](${src})\n\n*Processing attached image "${alt}" — grounding at correct bbox if requested…*\n\n`;
        })
        .join("\n");
      const insertIdx = events.findIndex((e) => e.event === "thinking_done");
      if (insertIdx !== -1) events.splice(insertIdx + 1, 0, { event: "answer_delta", payload: { chunk: imgBlocks } } as any);
      else events.splice(events.findIndex((e) => e.event === "answer_delta"), 0, { event: "answer_delta", payload: { chunk: imgBlocks } } as any);
    }
    await emitSequence(events, () => {});
    // detect scenario for follow-ups
    const sc = q.includes("water") || q.includes("locate agricultural") ? "grounding" : q.includes("visible") ? "vqa" : q.includes("optical") ? "fusion" : "coastal";
    attachFollowUps(sc);
    return;
  }
  const hasHistory = useSessionStore.getState().bboxes.length > 0;
  const isFollowUpStructure = hasHistory && /structure|inside|that |northern edge|building|small|surrounding it|what is surrounding/.test(q);
  const isVqa = /describe|land.cover|agricultural|fields|settlement|forested|what is visible|visible in this image/i.test(q);
  const isGrounding = /water|structure|building|bbox|ground|locate agricultural/i.test(q);
  const isChange = /change|coast|urban|expansion|shoreline|built-up.*increased/i.test(q);
  const isFusion = /sar|fusion|optical.*sar|sar.*optical|compare.*optical.*sar/i.test(q);

  let events: ExecutionEvent[];
  if (isFollowUpStructure) events = groundingCropSecondEvents();
  else if (isVqa && !isGrounding && !isChange && !isFusion) events = vqaEvents();
  else if (isGrounding && !isChange) events = groundingEvents();
  else if (isFusion) events = fusionEvents(query);
  else events = coastalChangeEvents();

  // If image/AOI contexts were attached, prepend their visualization — use real preview so chat shows inputted pixels
  const imgContexts = (_ctxRefs || []).filter((c: any) => c.type === "image" || c.type === "aoi" || c.preview);
  if (imgContexts.length > 0) {
    const imgBlocks = imgContexts
      .map((c: any) => {
        if (c.type === "aoi") return `> **AOI attached:** ${c.label} — will be used as spatial filter.\n\n`;
        const alt = c.label || c.fileName || "Attached image";
        const src = c.preview && String(c.preview).length > 10 ? String(c.preview) : `image:${c.id || alt.replace(/\s+/g, "-").toLowerCase()}`;
        return `![${alt}](${src})\n\n*Processing attached image "${alt}" — grounding at correct bbox if requested…*\n\n`;
      })
      .join("\n");
    // inject after thinking_done, before first answer_delta
    const insertIdx = events.findIndex((e) => e.event === "thinking_done");
    if (insertIdx !== -1) {
      events.splice(insertIdx + 1, 0, { event: "answer_delta", payload: { chunk: imgBlocks } } as any);
    } else {
      events.splice(events.findIndex((e) => e.event === "answer_delta"), 0, { event: "answer_delta", payload: { chunk: imgBlocks } } as any);
    }
  }

  await emitSequence(events, () => {});
  // attach follow-ups based on chosen scenario
  let sc2 = "coastal";
  if (isFollowUpStructure) sc2 = "crop";
  else if (isVqa && !isGrounding && !isChange && !isFusion) sc2 = "vqa";
  else if (isGrounding && !isChange) sc2 = "grounding";
  else if (isFusion) sc2 = "fusion";
  // reuse helper via lastId
  {
    const lastId = (emitSequence as any)._lastId as string | undefined;
    if (lastId && Math.random() >= 0.18) {
      const map2: Record<string, string[]> = {
        coastal: ["Break down change by sector", "What caused the retreat?", "Show built-up increase alone"],
        grounding: ["What is near this water body?", "Show confidence breakdown", "Find other water bodies"],
        fusion: ["Which modality was stronger?", "Show SAR texture alone", "Explain fusion confidence"],
        vqa: ["Count built-up clusters", "Describe vegetation health", "Where is the settlement?"],
        crop: ["Zoom to full water body", "What surrounds this structure?", "Estimate its area"],
      };
      const qs2 = map2[sc2] ?? ["Tell me more", "Show on map"];
      try { useChatStore.getState().setFollowUpQuestions(lastId, qs2.slice(0, 3)); } catch {}
    }
  }
}

export function getScenarioNames(): string[] {
  return ["coastal-change", "grounding", "fusion", "vqa", "grounding-crop-second", "multiturn"];
}
