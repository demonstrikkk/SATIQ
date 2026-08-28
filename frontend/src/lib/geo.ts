export type BBox = [number, number, number, number]; // normalized or xyxy

export function normalizeBboxToLngLat(bboxNorm: BBox, opts?: { center?: [number, number], span?: number }): [[number,number],[number,number]] {
  // converts normalized [x1,y1,x2,y2] (0-1) to lng/lat around center
  const center: [number,number] = opts?.center ?? [-80.37, 31.48];
  const span = opts?.span ?? 0.12;
  const [x1,y1,x2,y2] = bboxNorm;
  const minLng = center[0] - span/2 + x1*span;
  const maxLng = center[0] - span/2 + x2*span;
  const minLat = center[1] - span/2 + y1*span;
  const maxLat = center[1] - span/2 + y2*span;
  return [[minLng, minLat],[maxLng, maxLat]];
}

export function bboxToPolygon(bbox: BBox): any {
  const [[minLng, minLat],[maxLng, maxLat]] = Array.isArray(bbox[0]) ? bbox as unknown as [[number,number],[number,number]] : (()=>{ const [x1,y1,x2,y2]=bbox; return [[x1,y1],[x2,y2]] as [[number,number],[number,number]]})();
  return { type: "Polygon", coordinates: [[[minLng, minLat],[maxLng, minLat],[maxLng, maxLat],[minLng, maxLat],[minLng, minLat]]] };
}

export function parseBbox(bbox: number[]): BBox {
  if (bbox.length === 4) return bbox as BBox;
  return [0,0,0,0];
}

export function bboxCenter(bboxLngLat: [[number,number],[number,number]]): [number, number] {
  return [(bboxLngLat[0][0]+bboxLngLat[1][0])/2, (bboxLngLat[0][1]+bboxLngLat[1][1])/2];
}

export function featureIdFor(label: string, idx: number): string {
  return `${label.toLowerCase().replace(/\s+/g,"_")}_${String(idx).padStart(3,"0")}`;
}
