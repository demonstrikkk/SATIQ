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
    # MOCK_QWEN=true → never call Ollama, use deterministic heuristic (auditable, offline)
    mock_qwen: bool = Field(default=True, alias="MOCK_QWEN")
    # Auto switch: auto = try local Qwen → Groq → mock; local/groq/mock force specific provider
    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    # User has two Groq keys named GROQ_API_KEY1 / GROQ_API_KEY2 (see orchestrator/.env)
    groq_api_key1: str = Field(default="", alias="GROQ_API_KEY1")
    groq_api_key2: str = Field(default="", alias="GROQ_API_KEY2")
    groq_model: str = Field(default="qwen/qwen3.6-27b", alias="GROQ_MODEL")
    groq_router_model: str = Field(default="groq/compound-mini", alias="GROQ_ROUTER_MODEL")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    # Mistral workload split (optional third key)
    mistral_api_key: str = Field(default="", alias="MISTRAL_API_KEY")
    mistral_base_url: str = Field(default="https://api.mistral.ai/v1", alias="MISTRAL_BASE_URL")
    mistral_model: str = Field(default="mistral-small-latest", alias="MISTRAL_MODEL")
    # Voice-to-text (Groq Whisper)
    groq_stt_model: str = Field(default="whisper-large-v3", alias="GROQ_STT_MODEL")
    enable_voice: bool = Field(default=True, alias="ENABLE_VOICE")
    jwt_secret: str = Field(default="change-me", alias="JWT_SECRET")
    env: str = Field(default="development", alias="ENV")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    # --- Capability checkpoints (real models) — §2/§3 ---
    pretrained_dir: str = Field(default="capabilities/weights", alias="PRETRAINED_DIR")
    gdino_config: str = Field(default="capabilities/single_image/weights/gdino_swinb.cfg", alias="GDINO_CONFIG")
    gdino_weights: str = Field(default="capabilities/single_image/weights/gdino_swinb.pth", alias="GDINO_WEIGHTS")
    vqa_weights: str = Field(default="capabilities/single_image/weights/rs_llava.pth", alias="VQA_WEIGHTS")
    croma_weights: str = Field(default="capabilities/fusion/weights/croma.pth", alias="CROMA_WEIGHTS")
    change_stage1_ckpt: str = Field(default="capabilities/temporal/weights/stage1_final.pth", alias="CHANGE_STAGE1_CKPT")
    vicuna_weights: str = Field(default="capabilities/temporal/weights/vicuna-7b-v1.5", alias="VICUNA_WEIGHTS")
    image_size: int = Field(default=224, alias="IMAGE_SIZE")
    s2_percentile_low: float = Field(default=2.0, alias="S2_PERCENTILE_LOW")
    s2_percentile_high: float = Field(default=98.0, alias="S2_PERCENTILE_HIGH")

    model_config = {"env_file": ".env", "extra": "ignore", "populate_by_name": True}

@lru_cache
def get_settings() -> Settings:
    # allow orchestrator/.env relative to this file
    env_file = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_file):
        return Settings(_env_file=env_file)  # type: ignore
    return Settings()
