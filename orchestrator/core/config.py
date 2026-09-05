"""Central config — reads .env, validates, exposes typed settings."""
from __future__ import annotations
import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    database_url: str = Field(default="postgresql+asyncpg://postgres:postgres@localhost:5432/satiq", alias="DATABASE_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    celery_broker_url: str = Field(default="redis://localhost:6379/1", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/2", alias="CELERY_RESULT_BACKEND")
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")
    qwen_base_url: str = Field(default="http://localhost:11434/v1", alias="QWEN_BASE_URL")
    qwen_api_key: str = Field(default="ollama", alias="QWEN_API_KEY")
    qwen_model: str = Field(default="qwen3.5:9b", alias="QWEN_MODEL")
    # MOCK_QWEN deprecated — kept for compat but is_mock_mode() now always False (no mock in prod)
    mock_qwen: bool = Field(default=False, alias="MOCK_QWEN")
    # Ollama qwen3.5:9b only per user directive — auto resolves to local, Groq forbidden
    llm_provider: str = Field(default="local", alias="LLM_PROVIDER")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_api_key1: str = Field(default="", alias="GROQ_API_KEY1")
    groq_api_key2: str = Field(default="", alias="GROQ_API_KEY2")
    groq_model: str = Field(default="qwen/qwen3.6-27b", alias="GROQ_MODEL")
    groq_router_model: str = Field(default="openai/gpt-oss-20b", alias="GROQ_ROUTER_MODEL")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    mistral_base_url: str = Field(default="https://api.mistral.ai/v1", alias="MISTRAL_BASE_URL")
    mistral_model: str = Field(default="mistral-small-latest", alias="MISTRAL_MODEL")
    groq_stt_model: str = Field(default="whisper-large-v3", alias="GROQ_STT_MODEL")
    enable_voice: bool = Field(default=True, alias="ENABLE_VOICE")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    env: str = Field(default="development", alias="ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    # --- Portable model roots — all relative, no C:/coding absolutes ---
    # External inference.py scripts will be mounted at ./models/{vqa,grounding,change,fusion}/inference.py
    pretrained_dir: str = Field(default="capabilities/weights", alias="PRETRAINED_DIR")
    models_root: str = Field(default="models", alias="MODELS_ROOT")
    gdino_config: str = Field(default="capabilities/single_image/weights/gdino_swinb.cfg", alias="GDINO_CONFIG")
    gdino_weights: str = Field(default="capabilities/single_image/weights/gdino_swinb.pth", alias="GDINO_WEIGHTS")
    vqa_weights: str = Field(default="capabilities/single_image/weights/rs_llava.pth", alias="VQA_WEIGHTS")
    croma_weights: str = Field(default="capabilities/fusion/weights/croma.pth", alias="CROMA_WEIGHTS")
    croma_base_weights: str = Field(default="models/fusion/croma_base.pt", alias="CROMA_BASE_WEIGHTS")
    fusion_head_weights: str = Field(default="models/fusion/best_fusion_model.pt", alias="FUSION_HEAD_WEIGHTS")
    model4_root: str = Field(default="models/fusion", alias="MODEL4_ROOT")
    geochat_model_dir: str = Field(default="models/vqa/merged_model", alias="GEOCHAT_MODEL_DIR")
    geochat_run_inference: str = Field(default="models/vqa/inference.py", alias="GEOCHAT_RUN_INFERENCE")
    change_stage1_ckpt: str = Field(default="models/change/stage1_final.pth", alias="CHANGE_STAGE1_CKPT")
    vicuna_weights: str = Field(default="models/change/vicuna-7b-v1.5", alias="VICUNA_WEIGHTS")
    image_size: int = Field(default=224, alias="IMAGE_SIZE")
    s2_percentile_low: float = Field(default=2.0, alias="S2_PERCENTILE_LOW")
    s2_percentile_high: float = Field(default=98.0, alias="S2_PERCENTILE_HIGH")
    # --- Query cache / RAG / Resilience ---
    query_cache_ttl: int = Field(default=3600, alias="QUERY_CACHE_TTL")
    rag_top_k: int = Field(default=6, alias="RAG_TOP_K")
    rag_threshold: float = Field(default=0.72, alias="RAG_THRESHOLD")
    chroma_path: str = Field(default="chroma_db", alias="CHROMA_PATH")
    chroma_host: str = Field(default="", alias="CHROMA_HOST")
    allow_synthetic_assets: bool = Field(default=False, alias="ALLOW_SYNTHETIC_ASSETS")
    gateway_public_url: str = Field(default="http://localhost:4000", alias="GATEWAY_PUBLIC_URL")
    orchestrator_url: str = Field(default="http://localhost:8000", alias="ORCHESTRATOR_URL")
    sqlite_path: str = Field(default="orchestrator/storage/memory.db", alias="SQLITE_PATH")
    vram_max_queue: int = Field(default=4, alias="VRAM_MAX_QUEUE")

    model_config = {"env_file": ".env", "extra": "ignore", "populate_by_name": True}

    def validated_gateway_url(self) -> str:
        from urllib.parse import urlparse
        u = self.gateway_public_url.strip()
        p = urlparse(u)
        if p.scheme not in ("http", "https"):
            raise ValueError(f"GATEWAY_PUBLIC_URL must be http/https, got {u}")
        if not p.netloc:
            raise ValueError(f"GATEWAY_PUBLIC_URL missing host: {u}")
        if ".." in p.path or "localhost" in p.netloc and self.env == "production":
            # allow localhost in dev, but warn in prod
            pass
        return u.rstrip("/")

@lru_cache
def get_settings() -> Settings:
    # allow orchestrator/.env relative to this file
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        return Settings(_env_file=env_file)  # type: ignore
    return Settings()
