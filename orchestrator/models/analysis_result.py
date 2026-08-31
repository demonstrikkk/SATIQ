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
    confidence: Optional[float] = Field(default=None, ge=0, le=1, description="Real confidence or null per rule 7 — never invented")
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
    # additive extensions for real models (§2b, §5) — preserve existing consumers
    artifacts: Optional[List[Dict[str, Any]]] = Field(default=None, description="Visual evidence artifacts from visualisation_tool")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Pipeline mode, deltas, categories, etc.")
    pipeline_mode: Optional[str] = Field(default=None, description="stage1_index_hybrid for change_vqa etc.")
    error_code: Optional[str] = Field(default=None, description="MODEL_LOAD_ERROR etc. on failure")

# Specific outputs matching dummy structures in prompt
class VQAResult(BaseModel):
    task: Literal["vqa"] = "vqa"
    query: str
    image_id: str
    answer_text: str
    answer_type: Literal["open","closed"] = "open"
    answer_short: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

class GroundingResult(BaseModel):
    task: Literal["grounding"] = "grounding"
    query: str
    image_id: str
    bbox: List[float]  # xyxy normalized
    bbox_xyxy: List[int]
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    mask_rle: Optional[str] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

class ChangeVQAResult(BaseModel):
    task: Literal["change_vqa"] = "change_vqa"
    query: str
    image_t1_id: str
    image_t2_id: str
    answer_text: str
    change_categories: List[str]
    change_mask_rle: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    pipeline_mode: Optional[str] = None
    artifacts: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None

class FusionResult(BaseModel):
    task: Literal["optical_sar_fusion"] = "optical_sar_fusion"
    query: str
    optical_image_id: str
    sar_image_id: str
    answer_text: str
    class_map_rle: Optional[Dict[str, str]] = None
    per_modality_confidence: Optional[Dict[str, float]] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    artifacts: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None
