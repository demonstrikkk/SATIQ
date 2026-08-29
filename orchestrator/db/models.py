"""SQLAlchemy models — PostgreSQL+PostGIS ready, SQLite fallback for local dev."""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, Text, JSON, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Uuid

Base = declarative_base()

def _uuid():
    return str(uuid.uuid4())

def _now():
    return datetime.now(timezone.utc)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(String(36), primary_key=True, default=_uuid)
    user_id = Column(String(64), nullable=True)
    query = Column(Text, nullable=False)
    status = Column(String(32), default="queued")  # queued, running, completed, failed
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    meta = Column(JSON, nullable=True)

class Image(Base):
    __tablename__ = "images"
    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    modality = Column(String(32), nullable=False)  # optical, sar, multispectral
    crs = Column(String(64), nullable=True)  # EPSG:4326 etc
    gsd = Column(Float, nullable=True)
    bbox = Column(JSON, nullable=True)  # [minx,miny,maxx,maxy]
    bands = Column(JSON, nullable=True)
    acquired_at = Column(DateTime(timezone=True), nullable=True)
    minio_key = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

class Tile(Base):
    __tablename__ = "tiles"
    id = Column(String(36), primary_key=True, default=_uuid)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False, index=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    bbox = Column(JSON, nullable=True)
    status = Column(String(32), default="pending")  # pending, processing, done, failed
    created_at = Column(DateTime(timezone=True), default=_now)

class TaskOutput(Base):
    __tablename__ = "task_outputs"
    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False, index=True)
    task_type = Column(String(64), nullable=False)
    result = Column(JSON, nullable=False)
    confidence = Column(Float, nullable=True)
    execution_trace = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

class CoregRecord(Base):
    __tablename__ = "coreg_records"
    id = Column(String(36), primary_key=True, default=_uuid)
    session_id = Column(String(36), nullable=False, index=True)
    image_a_id = Column(String(36), nullable=True)
    image_b_id = Column(String(36), nullable=True)
    method = Column(String(64), default="dummy")
    ssim = Column(Float, nullable=True)
    residual = Column(Float, nullable=True)
    passed = Column(Integer, default=1)  # bool as int for sqlite compat
    created_at = Column(DateTime(timezone=True), default=_now)

class ImageEmbedding(Base):
    __tablename__ = "image_embeddings"
    id = Column(String(36), primary_key=True, default=_uuid)
    image_id = Column(String(36), ForeignKey("images.id"), nullable=False, index=True)
    tile_id = Column(String(36), ForeignKey("tiles.id"), nullable=True)
    model = Column(String(64), nullable=False)
    dim = Column(Integer, nullable=False)
    # pgvector would be Vector(dim); fallback JSON
    embedding = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

Index("idx_sessions_deleted_at", Session.deleted_at)
Index("idx_images_bbox_gin", Image.bbox)  # placeholder; real PostGIS GIST on geom
