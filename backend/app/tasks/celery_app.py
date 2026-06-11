from celery import Celery
from app.core.config import settings

celery_app = Celery("worker")

celery_app.conf.update(
    broker_url="sqs://",

    task_default_queue="image-processing-queue",

    broker_transport_options={
        "region": settings.AWS_REGION,
        "wait_time_seconds": 20,
        "visibility_timeout": 3600,
        "polling_interval": 1,
        "queue_name_prefix": "",
        "create_missing_queues": False,
        "predefined_queues": {}
    },

    task_acks_late=True,
    task_reject_on_worker_lost=True,

    result_backend=None
)