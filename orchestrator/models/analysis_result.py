"""Analysis result models — covers all 4 capability outputs."""
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

TaskType = Literal["vqa","grounding","change_vqa","optical_sar_fusion","captioning"]

class BBox(BaseModel):
    x: float
    y: float
    w: float
    h: float
    crs: Optional[str] = None

class ExecutionTraceStep(BaseModel):
    agent: str
    status: str  # ok, failed, skipped, retried
    latency_ms: Optional[int] = None
    detail: Optional[Dict[str, Any]] = None

class AnalysisResult(BaseModel):
    task: TaskType
    query: str
    answer_text: str
    confidence: float = Field(ge=0, le=1)
    execution_trace: List[ExecutionTraceStep] = Field(default_factory=list)
    chart_spec: Optional[Dict[str, Any]] = None  # apexcharts spec if numeric
    # optional evidence fields — present depending on task
    bbox: Optional[List[float]] = None  # [x,y,w,h] or xyxy normalized
    mask_rle: Optional[str] = None
    change_categories: Optional[List[str]] = None
    change_mask_rle: Optional[str] = None
    class_map_rle: Optional[Dict[str, str]] = None
    per_modality_confidence: Optional[Dict[str, float]] = None
    answer_type: Optional[Literal["open","closed"]] = None
    answer_short: Optional[str] = None

# Specific outputs matching dummy structures in prompt
class VQAResult(BaseModel):
    task: Literal["vqa"] = "vqa"
    query: str
    image_id: str
    answer_text: str
    answer_type: Literal["open","closed"] = "open"
    answer_short: Optional[str] = None
    confidence: float = Field(ge=0, le=1)

class GroundingResult(BaseModel):
    task: Literal["grounding"] = "grounding"
    query: str
    image_id: str
    bbox: List[float]  # xyxy normalized
    bbox_xyxy: List[int]
    confidence: float
    mask_rle: Optional[str] = None

class ChangeVQAResult(BaseModel):
    task: Literal["change_vqa"] = "change_vqa"
    query: str
    image_t1_id: str
    image_t2_id: str
    answer_text: str
    change_categories: List[str]
    change_mask_rle: Optional[str] = None
    confidence: float

class FusionResult(BaseModel):
    task: Literal["optical_sar_fusion"] = "optical_sar_fusion"
    query: str
    optical_image_id: str
    sar_image_id: str
    answer_text: str
    class_map_rle: Dict[str, str]
    per_modality_confidence: Dict[str, float]
