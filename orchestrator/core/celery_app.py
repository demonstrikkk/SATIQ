"""Celery app — defines required queues (dummy tasks for now). Queues mirror PHASE 1.4 spec."""
from __future__ import annotations
try:
    from celery import Celery  # type: ignore
except Exception:
    Celery = None  # type: ignore
from orchestrator.core.config import get_settings

def make_celery():
    if Celery is None:
        return None
    s = get_settings()
    app = Celery("satiq", broker=s.celery_broker_url, backend=s.celery_result_backend)
    app.conf.task_queues = {
        "preprocess": {"exchange": "preprocess"},
        "inference.encode": {"exchange": "inference.encode"},
        "inference.fusion": {"exchange": "inference.fusion"},
        "inference.task": {"exchange": "inference.task"},
        "postprocess": {"exchange": "postprocess"},
        "satellite.fetch": {"exchange": "satellite.fetch"},
    }
    app.conf.task_default_queue = "preprocess"
    return app

celery_app = make_celery()

# dummy tasks to satisfy flower / worker discovery
if celery_app is not None:
    @celery_app.task(name="satiq.preprocess", queue="preprocess")
    def task_preprocess(payload: dict):
        return {"status": "ok", "payload": payload}

    @celery_app.task(name="satiq.encode", queue="inference.encode")
    def task_encode(payload: dict):
        return {"status": "ok"}

    @celery_app.task(name="satiq.fusion", queue="inference.fusion")
    def task_fusion(payload: dict):
        return {"status": "ok"}

    @celery_app.task(name="satiq.task_agent", queue="inference.task")
    def task_task(payload: dict):
        return {"status": "ok"}

    @celery_app.task(name="satiq.postprocess", queue="postprocess")
    def task_postprocess(payload: dict):
        return {"status": "ok"}
