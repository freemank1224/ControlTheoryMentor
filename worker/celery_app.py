"""
Celery application configuration for the AI Tutor Worker service
"""
from celery import Celery
from os import getenv
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

celery_app = Celery(
    'ai_tutor_worker',
    broker=getenv('REDIS_URL', 'redis://localhost:6379/0'),
    backend=getenv('REDIS_URL', 'redis://localhost:6379/0'),
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max per task
    task_soft_time_limit=3000,  # 50 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
)

celery_app.conf.task_routes = {
    'worker.tasks.process_pdf_task': {'queue': 'pdf_processing'},
    'worker.tasks.generate_graph_task': {'queue': 'graph_generation'},
}
