"""Pydantic models for raster assets — build first per README priority."""
from __future__ import annotations
from typing import List, Optional, Literal, Tuple
from pydantic import BaseModel, Field, field_validator
import re

Modality = Literal["optical", "sar", "multispectral", "unknown"]
CRS_PATTERN = re.compile(r"^(EPSG:\d+|CRS:84|OGC:CRS84)$", re.IGNORECASE)

class RasterAsset(BaseModel):
    asset_id: str = Field(description="Unique asset id, e.g. img_001 or UUID")
    filename: str
    modality: Modality = "unknown"
    crs: Optional[str] = Field(default=None, description="EPSG code string, e.g. EPSG:4326")
    gsd: Optional[float] = Field(default=None, description="Ground sampling distance in meters", ge=0)
    bbox: Optional[Tuple[float,float,float,float]] = Field(default=None, description="[minx,miny,maxx,maxy]")
    bands: Optional[List[str]] = Field(default=None, description="Band names, e.g. [B02,B03,B04]")
    width: Optional[int] = Field(default=None, ge=1)
    height: Optional[int] = Field(default=None, ge=1)
    acquired_at: Optional[str] = None  # ISO8601
    minio_key: Optional[str] = None

    @field_validator("crs")
    @classmethod
    def validate_crs(cls, v):
        if v is None:
            return v
        if not CRS_PATTERN.match(v.strip()):
            # allow EPSG:326xx etc; still require prefix
            if not v.upper().startswith("EPSG:"):
                raise ValueError(f"CRS must be EPSG:xxxx, got {v}")
        return v.upper() if v.upper().startswith("EPSG:") else v

class InputSchema(BaseModel):
    """POST /api/v1/task payload — validates before LLM."""
    query: str = Field(min_length=1, max_length=4000, description="Natural language question")
    image_ids: Optional[List[str]] = Field(default=None, description="Single image task: 1 id")
    image_t1_id: Optional[str] = None
    image_t2_id: Optional[str] = None
    optical_image_id: Optional[str] = None
    sar_image_id: Optional[str] = None
    assets: Optional[List[RasterAsset]] = None  # alternative to ids, carries metadata for validator

    @field_validator("query")
    @classmethod
    def strip_query(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("query must be non-empty")
        return v

class StepPlan(BaseModel):
    """Planner output — forced JSON from Qwen."""
    task_type: Literal["vqa","grounding","change_vqa","optical_sar_fusion","captioning"] = Field(description="Normalized task")
    reasoning: str = Field(description="Short planner reasoning")
    required_assets: List[str] = Field(default_factory=list)
    fusion_needed: bool = False
    temporal_needed: bool = False
    confidence: float = Field(default=0.8, ge=0, le=1)
