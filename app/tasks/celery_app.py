"""
Celery application configuration.
"""
from celery import Celery
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# Create Celery app
celery_app = Celery(
    "threat_intel_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.ingestion",
    ],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
)


@celery_app.task(bind=True, name="health_check")
def health_check(self):
    """Health check task."""
    return {"status": "healthy"}


@celery_app.task(bind=True, name="test_task")
def test_task(self, *args, **kwargs):
    """Test task for verification."""
    logger.info("Test task executed", args=args, kwargs=kwargs)
    return {"result": "success"}
