import { create } from "zustand";
interface UiState {
  layerPanelOpen: boolean;
  evidenceGraphOpen: boolean;
  setLayerPanelOpen: (v: boolean)=>void;
  setEvidenceGraphOpen: (v: boolean)=>void;
}
export const useUiStore = create<UiState>((set)=>({
  layerPanelOpen: false,
  evidenceGraphOpen: false,
  setLayerPanelOpen: (v)=> set({ layerPanelOpen: v }),
  setEvidenceGraphOpen: (v)=> set({ evidenceGraphOpen: v }),
}));
