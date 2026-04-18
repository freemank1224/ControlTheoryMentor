from celery import Celery

from app.config import settings


TASK_PROCESS_PDF = "worker.tasks.process_pdf_task"


_celery_app: Celery | None = None


def get_celery_app() -> Celery:
    global _celery_app

    if _celery_app is None:
        _celery_app = Celery(
            "control_theory_mentor_backend",
            broker=settings.REDIS_URL,
            backend=settings.REDIS_URL,
        )

    return _celery_app