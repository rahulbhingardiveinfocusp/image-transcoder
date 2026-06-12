import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery("worker")

# Build the SQS endpoint dynamically if using LocalStack, otherwise default to standard SQS
endpoint_url = (settings.LOCALSTACK_ENDPOINT or "").strip() or None

celery_app.conf.update(
    # If using LocalStack, Celery needs the square bracket format: sqs://@localhost:4566
    broker_url=f"sqs://@{endpoint_url.split('//')[-1]}" if endpoint_url else "sqs://",

    # Dedicate this worker to the Celery task queue
    task_default_queue=settings.CELERY_QUEUE_NAME,

    broker_transport_options={
        "region": settings.AWS_REGION,
        "wait_time_seconds": 20,       # Long polling (good for reducing AWS API costs)
        "visibility_timeout": 3600,    # 1 hour to allow heavy processing tasks to finish
        "polling_interval": 1,
        "queue_name_prefix": "",
        "create_missing_queues": False, # Infrastructure should be managed via AWS/Terraform
        "predefined_queues": {
            settings.CELERY_QUEUE_NAME: {
                "url": settings.CELERY_TASK_QUEUE_URL 
            }
        }
    },

    # Task reliability settings (safe for image manipulation pipelines)
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    result_backend=None  # Optimized: No backend overhead since tasks finish statefully in S3/DB
)

# Discover tasks automatically
celery_app.autodiscover_tasks(["app.tasks"])