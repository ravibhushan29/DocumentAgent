"""Celery settings: Redis broker, result backend, retries (Section 8)."""

from app.core.config import get_settings

settings = get_settings()

broker_url = settings.REDIS_URL.replace("/0", f"/{settings.REDIS_CELERY_RESULT_DB}")
result_backend = broker_url

task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]

task_acks_late = True
task_reject_on_worker_lost = True
worker_prefetch_multiplier = 1

task_routes = {
    "workers.tasks.ingest_document": {"queue": "ingestion"},
}
task_default_queue = "default"

task_max_retries = 5
task_default_retry_delay = 30  # seconds; plan uses exponential 1,2,4,8,16

timezone = "UTC"
enable_utc = True
