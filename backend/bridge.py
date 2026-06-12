import boto3
import json
import time
import logging
import sys
from app.tasks.image_tasks import process_s3_upload_task
from app.core.config import settings  

# Setup unbuffered, explicit logging for easier AWS CloudWatch/Docker log viewing
logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [BRIDGE-SCRIPT] %(message)s"
)
logger = logging.getLogger(__name__)

endpoint_url = (settings.LOCALSTACK_ENDPOINT or "").strip() or None

sqs = boto3.client(
    "sqs",
    region_name=settings.AWS_REGION,
    endpoint_url=endpoint_url
)

# Reusing your central raw S3 notifications queue setting
S3_EVENTS_QUEUE = settings.SQS_QUEUE_URL

logger.info(f"Bridge gateway active. Listening on S3 events queue: {S3_EVENTS_QUEUE}")

while True:
    try:
        response = sqs.receive_message(QueueUrl=S3_EVENTS_QUEUE, WaitTimeSeconds=20)
        if 'Messages' in response:
            for msg in response['Messages']:
                logger.info(f"Received event message ID: {msg['MessageId']}")
                try:
                    body = json.loads(msg['Body'])
                except json.JSONDecodeError:
                    logger.warning(f"Skipping non-JSON message: {msg['MessageId']}")
                    sqs.delete_message(QueueUrl=S3_EVENTS_QUEUE, ReceiptHandle=msg['ReceiptHandle'])
                    continue
                
                # Verify message contains structural S3 notification records
                if "Records" in body:
                    for record in body['Records']:
                        bucket = record["s3"]["bucket"]["name"]
                        key = record["s3"]["object"]["key"]
                        
                        # FILTER: Only route files coming directly from the 'raw/' folder
                        if key.startswith("raw/"):
                            logger.info(f"[+] Match found! Dispatching Celery task for: s3://{bucket}/{key}")
                            process_s3_upload_task.delay(bucket, key)
                        else:
                            logger.info(f"[-] Ignoring file: {key} (Target outside 'raw/' folder)")
                
                # Delete message from S3 queue after handling/skipping to prevent infinite processing loops
                sqs.delete_message(
                    QueueUrl=S3_EVENTS_QUEUE, 
                    ReceiptHandle=msg['ReceiptHandle']
                )
    except Exception as e:
        logger.error(f"Execution error in bridge main loop: {e}")
        time.sleep(5)