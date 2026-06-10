from celery import Celery
from app.core.config import settings

celery_app = Celery("image_worker")

celery_app.conf.update(
    broker_url="sqs://",
    task_default_queue="image-processing-queue",
    broker_transport_options={
        "region": settings.AWS_REGION,
        "wait_time_seconds": 20,
        "visibility_timeout": 3600,
    },
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)