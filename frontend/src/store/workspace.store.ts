import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export interface PersistedSession {
  id: string;
  title: string;
  category: "change" | "fusion" | "grounding" | "vqa" | "wildfire" | string;
  createdAt: string;
  updatedAt: string;
}

const SEED: PersistedSession[] = [
  { id: "coastal-change-2023-019", title: "Coastal erosion — Gulf Coast", category: "change", createdAt: new Date(Date.now() - 2 * 3600 * 1000).toISOString(), updatedAt: new Date(Date.now() - 2 * 3600 * 1000).toISOString() },
  { id: "crop-stress-iv-2024", title: "Crop stress — Imperial Valley", category: "vqa", createdAt: new Date(Date.now() - 24 * 3600 * 1000).toISOString(), updatedAt: new Date(Date.now() - 24 * 3600 * 1000).toISOString() },
  { id: "wildfire-nwt-2024", title: "Wildfire burn scar — NWT", category: "change", createdAt: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString(), updatedAt: new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString() },
  { id: "optical-sar-fusion-001", title: "Optical+SAR fusion — Wetland", category: "fusion", createdAt: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(), updatedAt: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString() },
  { id: "grounding-north-water-001", title: "Water body grounding — North", category: "grounding", createdAt: new Date(Date.now() - 4 * 3600 * 1000).toISOString(), updatedAt: new Date(Date.now() - 4 * 3600 * 1000).toISOString() },
];

interface WorkspaceState {
  sidebarOpen: boolean;
  inspectorOpen: boolean;
  commandOpen: boolean;
  activeAnalysisId: string | null;
  sessions: PersistedSession[];
  toggleSidebar: () => void;
  toggleInspector: () => void;
  setCommandOpen: (v: boolean) => void;
  setActiveAnalysisId: (id: string | null) => void;
  createSession: (title?: string) => string;
  renameSession: (id: string, title: string) => void;
  deleteSession: (id: string) => void;
  touchSession: (id: string) => void;
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set, get) => ({
      sidebarOpen: true,
      inspectorOpen: true,
      commandOpen: false,
      activeAnalysisId: "coastal-change-2023-019",
      sessions: SEED,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
      toggleInspector: () => set((s) => ({ inspectorOpen: !s.inspectorOpen })),
      setCommandOpen: (v) => set({ commandOpen: v }),
      setActiveAnalysisId: (id) => {
        if (id) get().touchSession(id);
        set({ activeAnalysisId: id });
      },
      createSession: (title) => {
        const id = `sess_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 6)}`;
        const now = new Date().toISOString();
        const session: PersistedSession = {
          id,
          title: title?.trim() ? title.trim().slice(0, 60) : `Chat ${new Date().toLocaleDateString()}`,
          category: "vqa",
          createdAt: now,
          updatedAt: now,
        };
        set((s) => ({ sessions: [session, ...s.sessions], activeAnalysisId: id }));
        // stash empty message list for new session
        try {
          localStorage.setItem(`satiq:session:${id}:messages`, JSON.stringify([]));
        } catch {}
        return id;
      },
      renameSession: (id, title) =>
        set((s) => ({
          sessions: s.sessions.map((x) => (x.id === id ? { ...x, title: title.slice(0, 60), updatedAt: new Date().toISOString() } : x)),
        })),
      deleteSession: (id) =>
        set((s) => {
          const next = s.sessions.filter((x) => x.id !== id);
          const active = s.activeAnalysisId === id ? (next[0]?.id ?? null) : s.activeAnalysisId;
          try {
            localStorage.removeItem(`satiq:session:${id}:messages`);
          } catch {}
          return { sessions: next, activeAnalysisId: active };
        }),
      touchSession: (id) =>
        set((s) => ({
          sessions: s.sessions.map((x) => (x.id === id ? { ...x, updatedAt: new Date().toISOString() } : x)),
        })),
    }),
    {
      name: "satiq-workspace-v1",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({ sidebarOpen: s.sidebarOpen, inspectorOpen: s.inspectorOpen, activeAnalysisId: s.activeAnalysisId, sessions: s.sessions }),
      version: 1,
    }
  )
);
