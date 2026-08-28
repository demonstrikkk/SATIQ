import type { Analysis } from "@/schemas/analysis";
export const analyses: Analysis[] = [
  { id:"coastal-change-2023-019", title:"Coastal erosion — Gulf Coast", category:"change", createdAt: new Date(Date.now()-2*3600*1000).toISOString(), status:"completed", confidence:0.87 },
  { id:"crop-stress-iv-2024", title:"Crop stress — Imperial Valley", category:"vqa", createdAt: new Date(Date.now()-24*3600*1000).toISOString(), status:"completed", confidence:0.82 },
  { id:"wildfire-nwt-2024", title:"Wildfire burn scar — NWT", category:"change", createdAt: new Date(Date.now()-2*24*3600*1000).toISOString(), status:"completed", confidence:0.91 },
  { id:"optical-sar-fusion-001", title:"Optical+SAR fusion — Wetland", category:"fusion", createdAt: new Date(Date.now()-3*24*3600*1000).toISOString(), status:"completed", confidence:0.88 },
  { id:"grounding-north-water-001", title:"Water body grounding — North", category:"grounding", createdAt: new Date(Date.now()-4*3600*1000).toISOString(), status:"completed", confidence:0.87 },
];
