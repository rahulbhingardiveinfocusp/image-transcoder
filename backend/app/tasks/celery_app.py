from celery import Celery
from app.core.config import settings

celery_app = Celery("worker")

celery_app.conf.update(
    broker_url="sqs://",
    task_default_queue=settings.SQS_QUEUE_URL,
    broker_transport_options={
        "region": settings.AWS_REGION,
        "visibility_timeout": 3600,
        "polling_interval": 5,
    },
    task_acks_late=True,
)