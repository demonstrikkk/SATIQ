import { create } from "zustand";

interface WorkspaceState {
  sidebarOpen: boolean;
  inspectorOpen: boolean;
  commandOpen: boolean;
  activeAnalysisId: string | null;
  toggleSidebar: () => void;
  toggleInspector: () => void;
  setCommandOpen: (v: boolean) => void;
  setActiveAnalysisId: (id: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  sidebarOpen: true,
  inspectorOpen: true,
  commandOpen: false,
  activeAnalysisId: "coastal-change-2023-019",
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
  toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
  setCommandOpen: (v) => set({ commandOpen: v }),
  setActiveAnalysisId: (id) => set({ activeAnalysisId: id }),
}));
