import { create } from "zustand";

export interface SessionTurn {
  id: string;
  turn: number;
  query: string;
  bbox_xyxy?: [number, number, number, number];
  bbox_normalized?: [number, number, number, number];
  label?: string;
  confidence?: number;
  imageId?: string;
  crop_target?: [number, number, number, number] | null;
}

export interface SpatialState {
  bboxes: Array<{ id: string; label: string; bbox_xyxy: [number, number, number, number]; bbox_normalized: [number, number, number, number]; confidence: number; turn: number }>;
  masks: Array<{ id: string; rle: string | null }>;
  history: SessionTurn[];
  lastCrop: [number, number, number, number] | null;
}

interface SessionState extends SpatialState {
  addTurn: (t: SessionTurn) => void;
  addBbox: (b: SpatialState["bboxes"][number]) => void;
  setLastCrop: (b: [number, number, number, number] | null) => void;
  clear: () => void;
}

export const useSessionStore = create<SessionState>((set) => ({
  bboxes: [],
  masks: [],
  history: [],
  lastCrop: null,
  addTurn: (t) => set((s) => ({ history: [...s.history, t] })),
  addBbox: (b) => set((s) => ({ bboxes: [...s.bboxes.filter(x => x.id !== b.id), b] })),
  setLastCrop: (lastCrop) => set({ lastCrop }),
  clear: () => set({ bboxes: [], masks: [], history: [], lastCrop: null }),
}));
