from celery import Celery

# Use a standard task queue name
celery_app = Celery("image_worker")

celery_app.conf.update(
    broker_url="sqs://elasticmq:elasticmq@localstack:4566/000000000000/celery-tasks",
    task_default_queue="celery-tasks",
    broker_transport_options={
        "region": "us-east-1",
        "endpoint_url": "http://localstack:4566",
    }
)