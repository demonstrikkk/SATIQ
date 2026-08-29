"""MinIO wrapper with local-disk fallback (so pipeline works without MinIO)."""
from __future__ import annotations
import os
from pathlib import Path

try:
    from minio import Minio  # type: ignore
except Exception:
    Minio = None  # type: ignore

from orchestrator.core.config import get_settings

BUCKETS = ["rs-raw","rs-processed","rs-outputs","rs-models"]

class MinioClient:
    def __init__(self):
        s = get_settings()
        self.endpoint = s.minio_endpoint
        self.access = s.minio_access_key
        self.secret = s.minio_secret_key
        self.secure = s.minio_secure
        self._client = None
        if Minio is not None:
            try:
                self._client = Minio(self.endpoint, access_key=self.access, secret_key=self.secret, secure=self.secure)
                # quick check
                # self._client.list_buckets()
            except Exception:
                self._client = None
        self.fallback_dir = Path("orchestrator/storage")
        self.fallback_dir.mkdir(parents=True, exist_ok=True)

    def ensure_buckets(self):
        if not self._client:
            for b in BUCKETS:
                (self.fallback_dir / b).mkdir(parents=True, exist_ok=True)
            return
        for b in BUCKETS:
            try:
                if not self._client.bucket_exists(b):
                    self._client.make_bucket(b)
            except Exception:
                pass

    def upload_bytes(self, bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream"):
        self.ensure_buckets()
        if self._client:
            try:
                import io
                self._client.put_object(bucket, key, io.BytesIO(data), len(data), content_type=content_type)
                return f"{bucket}/{key}"
            except Exception as e:
                print(f"[minio fallback] {e}")
        # fallback to disk
        p = self.fallback_dir / bucket / key
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return str(p)

    def download_bytes(self, bucket: str, key: str) -> bytes | None:
        if self._client:
            try:
                import io
                obj = self._client.get_object(bucket, key)
                return obj.read()
            except Exception:
                pass
        p = self.fallback_dir / bucket / key
        if p.exists():
            return p.read_bytes()
        return None

minio_client = MinioClient()
