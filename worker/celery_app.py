"""Celery application configuration for the Graphify worker."""

from __future__ import annotations

from os import getenv

from celery import Celery
from dotenv import load_dotenv

load_dotenv()


def _optional_positive_int_env(name: str) -> int | None:
    raw = getenv(name)
    if raw is None:
        return None
    value = int(raw)
    if value <= 0:
        return None
    return value

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
    # Long-running PDF extraction should not be killed by fixed defaults.
    task_time_limit=_optional_positive_int_env("CELERY_TASK_TIME_LIMIT"),
    task_soft_time_limit=_optional_positive_int_env("CELERY_TASK_SOFT_TIME_LIMIT"),
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_queue="pdf_processing",
    task_default_routing_key="pdf_processing",
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": int(getenv("CELERY_VISIBILITY_TIMEOUT", "43200")),
    },
    result_backend_transport_options={
        "visibility_timeout": int(getenv("CELERY_VISIBILITY_TIMEOUT", "43200")),
    },
)

celery_app.conf.task_routes = {
    "worker.tasks.process_pdf_task": {"queue": "pdf_processing"},
}

celery_app.autodiscover_tasks(["worker"])

import worker.tasks  # noqa: E402,F401
