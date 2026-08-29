"""Canonical model interface — both dummy and real models must satisfy this Protocol.

Teammate's real checkpoints (SatMAE, SSL4EO, Prithvi, CROMA) should implement these
interfaces; orchestrator remains model-agnostic and only depends on this contract.
"""
from __future__ import annotations
from typing import Protocol, TypedDict, Dict, Any, List, Optional
import numpy as np  # type: ignore
from typing import Literal

EncoderId = Literal["satmae","ssl4eo","prithvi","croma"]

class EncoderOutput(TypedDict, total=False):
    embeddings: Dict[str, Any]  # tile_id -> float32[dim] ndarray
    dim: int
    encoder_used: str
    per_tile_confidence: Dict[str, float]  # NEW: cloud/SAR noise quality 0-1
    attention_maps: Optional[Dict[str, Any]]  # tile_id -> float32[H,W] for grounding heatmap

class EncoderInterface(Protocol):
    def encode(self, tiles: List[Dict[str, Any]], modality: str, encoder_id: EncoderId) -> EncoderOutput: ...

class FusionOutput(TypedDict, total=False):
    fused_repr: Any  # ndarray or str dummy
    fusion_method: str
    confidence: float
    dim: int
    per_tile_weights: Optional[Dict[str, float]]  # NEW: weight per tile in fusion

class FusionInterface(Protocol):
    def fuse(self, optical_emb: Dict[str, Any], sar_emb: Dict[str, Any], query: str, method: str) -> FusionOutput: ...

class TaskOutput(TypedDict, total=False):
    # common
    task: str
    query: str
    answer_text: str
    confidence: float
    # grounding
    bbox_list: List[List[float]]
    phrase_grounding_map: Dict[str, List[List[float]]]
    mask_rle: Optional[str]
    attention_maps: Optional[Dict[str, Any]]
    # change
    change_categories: List[str]
    change_magnitude_pct: Optional[float]
    severity: Optional[str]
    change_mask_rle: Optional[str]
    # fusion
    class_map_rle: Dict[str, str]
    per_modality_confidence: Dict[str, float]
    # numeric
    answer_numeric: Optional[float]
    answer_unit: Optional[str]  # km², ha, count, percent
    answer_temporal_ref: Optional[str]
    # generic
    per_tile_confidence: Dict[str, float]

class TaskInterface(Protocol):
    def run(self, fused_repr: Any, task_type: str, query: str, metadata: Dict[str, Any]) -> TaskOutput: ...

# helper to wrap existing dummy functions to satisfy protocol
def wrap_dummy_encoder_output(embeddings: Dict[str, Any], encoder_id: str) -> EncoderOutput:
    # embeddings is {model: list[ndarray]} or {optical: [...]}
    # build per_tile_confidence dummy 0.85-0.95
    import random as _r
    per_tile: Dict[str, float] = {}
    # flatten counting
    cnt = 0
    for k, v in embeddings.items():
        if isinstance(v, list):
            for i, arr in enumerate(v):
                per_tile[f"{k}_{i}"] = round(0.85 + _r.Random(hash(k)+i).random()*0.10, 3)
                cnt += 1
        elif isinstance(v, dict) and "count" in v:
            cnt += int(v.get("count", 0))
    # attention maps: dummy None (real model would return heatmaps)
    return {
        "embeddings": embeddings,
        "dim": 768,
        "encoder_used": encoder_id,
        "per_tile_confidence": per_tile,
        "attention_maps": None,
    }

def wrap_dummy_fusion_output(fused: Dict[str, Any]) -> FusionOutput:
    return {
        "fused_repr": fused.get("fused_repr"),
        "fusion_method": fused.get("fusion_method","attention"),
        "confidence": fused.get("confidence",0.82),
        "dim": fused.get("dim",768),
        "per_tile_weights": None,
    }
