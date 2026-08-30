"""Voice-to-text via Groq whisper-large-v3. No frontend — backend service only.
Uses Groq OpenAI-compatible audio transcription endpoint.
"""
from __future__ import annotations
import io
import os
from typing import Optional, Dict, Any

from orchestrator.core.config import get_settings

def _pick_transcribe_key() -> str | None:
    s = get_settings()
    # prefer GROQ_KEY1, fallback to any groq key
    for cand in [
        getattr(s, "groq_api_key1", ""),
        getattr(s, "groq_api_key", ""),
        getattr(s, "groq_api_key2", ""),
        os.getenv("GROQ_API_KEY1", ""),
        os.getenv("GROQ_API_KEY", ""),
        os.getenv("GROQ_API_KEY2", ""),
    ]:
        if cand and cand.strip():
            return cand.strip()
    return None

def get_groq_client():
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    s = get_settings()
    key = _pick_transcribe_key()
    if not key:
        return None
    try:
        return OpenAI(base_url=s.groq_base_url, api_key=key)  # type: ignore
    except Exception:
        return None

def transcribe_audio(
    file_bytes: bytes,
    filename: str = "audio.wav",
    language: Optional[str] = None,
    prompt: Optional[str] = None,
    temperature: float = 0.0,
) -> Dict[str, Any]:
    """Transcribe audio bytes via Groq whisper-large-v3.
    Returns {"text": str, "language": str, "duration": float, "_provider": str, "_mock": bool}
    """
    s = get_settings()
    if not s.enable_voice:
        return {"text": "", "error": "voice disabled (ENABLE_VOICE=false)", "_provider": "disabled", "_mock": True}

    # Mock if no key
    if not _pick_transcribe_key():
        # deterministic mock transcription for offline testing
        return {
            "text": "Describe the land-cover and major objects visible in this image.",
            "language": language or "en",
            "duration": 2.1,
            "_provider": "mock",
            "_mock": True,
            "_note": "No GROQ_API_KEY — returning dummy transcription. Set GROQ_API_KEY to use whisper-large-v3.",
        }

    cli = get_groq_client()
    if cli is None:
        return {"text": "", "error": "groq client unavailable", "_provider": "mock", "_mock": True}

    try:
        # Groq whisper-large-v3 is OpenAI-compatible: audio.transcriptions.create
        # Use file tuple (filename, bytes, mime)
        # Detect mime from extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "wav"
        mime_map = {"wav": "audio/wav", "mp3": "audio/mpeg", "m4a": "audio/m4a", "ogg": "audio/ogg", "flac": "audio/flac", "webm": "audio/webm"}
        mime = mime_map.get(ext, "audio/wav")
        file_obj = (filename, io.BytesIO(file_bytes), mime)

        # Groq supports whisper-large-v3, whisper-large-v3-turbo; we use configured model
        kwargs: Dict[str, Any] = {
            "model": s.groq_stt_model,
            "file": file_obj,  # type: ignore
            "response_format": "json",
            "temperature": temperature,
        }
        if language:
            kwargs["language"] = language
        if prompt:
            kwargs["prompt"] = prompt

        # Use OpenAI SDK's audio transcription; Groq mirrors it
        result = cli.audio.transcriptions.create(**kwargs)  # type: ignore
        # result may be object with .text or dict
        text = getattr(result, "text", None) or (result.get("text") if isinstance(result, dict) else "") or ""
        lang = getattr(result, "language", None) or language or "en"
        duration = getattr(result, "duration", None) or 0.0
        return {
            "text": text,
            "language": lang,
            "duration": duration,
            "x_groq_id": getattr(result, "id", None) or getattr(result, "x_groq", None),
            "_provider": "groq",
            "_model": s.groq_stt_model,
            "_mock": False,
        }
    except Exception as e:
        # Fallback mock on error, but log
        print(f"[groq stt fallback] {e}")
        return {
            "text": "",
            "error": str(e)[:300],
            "_provider": "groq",
            "_mock": True,
            "_fallback": True,
        }

def transcribe_file(path: str, **kwargs) -> Dict[str, Any]:
    with open(path, "rb") as f:
        data = f.read()
    return transcribe_audio(data, filename=os.path.basename(path), **kwargs)
