from celery import Celery
from app.core.config import settings


celery_app = Celery("image_worker")
celery_app.conf.update(
    broker_url=settings.SQS_QUEUE_URL, 
    task_default_queue="image-processing-queue",
    broker_transport_options={
        "region": settings.AWS_REGION,
        "endpoint_url": settings.LOCALSTACK_ENDPOINT,
        "preconditions": {"sqs": {"wait_time_seconds": 20}},
    },
    # Ensure tasks are acknowledged only after completion
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)