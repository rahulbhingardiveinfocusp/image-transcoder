import logging
from celery import Celery
from app.core.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery("worker")

endpoint_url = (settings.LOCALSTACK_ENDPOINT or "").strip() or None

celery_app.conf.update(
    broker_url=f"sqs://@{endpoint_url.split('//')[-1]}" if endpoint_url else "sqs://",

    task_default_queue=settings.CELERY_QUEUE_NAME,

    broker_transport_options={
        "region": settings.AWS_REGION,
        "wait_time_seconds": 20,       
        "visibility_timeout": 3600,    
        "polling_interval": 1,
        "queue_name_prefix": "",
        "create_missing_queues": False, 
        "predefined_queues": {
            settings.CELERY_QUEUE_NAME: {
                "url": settings.CELERY_TASK_QUEUE_URL 
            }
        }
    },

   
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    result_backend=None  
)

celery_app.autodiscover_tasks(["app.tasks"])