"""Celery application configuration for the Graphify worker."""

from __future__ import annotations

from os import getenv

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

celery_app = Celery(
    "ai_tutor_worker",
    broker=getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

celery_app.conf.task_routes = {
    "worker.tasks.process_pdf_task": {"queue": "pdf_processing"},
}

celery_app.autodiscover_tasks(["worker"])

import worker.tasks  # noqa: E402,F401
