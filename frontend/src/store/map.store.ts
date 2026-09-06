import { create } from "zustand";

export interface SpatialFeature {
  id: string;
  label: string;
  confidence: number;
  source: string;
  turn?: number;
  imageId?: string;
  bboxNorm?: [number, number, number, number];
  lngLat?: [[number, number],[number, number]];
  type: "bbox"|"polygon"|"mask";
}

interface MapState {
  center: [number, number];
  zoom: number;
  bearing: number;
  pitch: number;
  activeBasemap: "satellite"|"street"|"terrain";
  layers: { imagery: boolean; detections: boolean; segmentation: boolean; changeMask: boolean; sar: boolean; };
  selectedFeatureId: string | null;
  features: SpatialFeature[];
  setCenter: (c:[number,number])=>void;
  setZoom: (z:number)=>void;
  setActiveBasemap: (b: MapState["activeBasemap"])=>void;
  toggleLayer: (k: keyof MapState["layers"])=>void;
  setSelectedFeatureId: (id: string|null)=>void;
  addFeature: (f: SpatialFeature)=>void;
  clearFeatures: ()=>void;
}

export const useMapStore = create<MapState>((set)=>({
  center: [-80.37, 31.48],
  zoom: 10,
  bearing: 0, pitch: 0,
  activeBasemap: "satellite",
  layers: { imagery:true, detections:true, segmentation:true, changeMask:false, sar:false },
  selectedFeatureId: null,
  features: [],
  setCenter: (center)=> set({ center }),
  setZoom: (zoom)=> set({ zoom }),
  setActiveBasemap: (activeBasemap)=> set({ activeBasemap }),
  toggleLayer: (layer)=> set((s)=> ({ layers:{ ...s.layers, [layer]: !s.layers[layer]}})),
  setSelectedFeatureId: (selectedFeatureId)=> set({ selectedFeatureId }),
  addFeature: (f)=> set((s)=> ({ features: [...s.features.filter(x=> x.id!==f.id), f]})),
  clearFeatures: ()=> set({ features: [] }),
}));
