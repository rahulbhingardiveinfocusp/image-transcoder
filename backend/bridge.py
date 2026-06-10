import boto3
import json
import time
from app.tasks.image_tasks import process_s3_upload_task
from app.core.config import settings  # Import your central settings object
endpoint_url = settings.LOCALSTACK_ENDPOINT or None
# Use settings from your config file
sqs = boto3.client(
    "sqs",
    region_name=settings.AWS_REGION,
    endpoint_url=endpoint_url
)
# Use the URL from settings
S3_EVENTS_QUEUE = settings.SQS_QUEUE_URL

print(f"Bridge running... Listening on: {S3_EVENTS_QUEUE}")

while True:
    try:
        response = sqs.receive_message(QueueUrl=S3_EVENTS_QUEUE, WaitTimeSeconds=20)
        if 'Messages' in response:
            for msg in response['Messages']:
                print(f"[*] Received message")
                body = json.loads(msg['Body'])
                
                # Check for S3 notification records
                if "Records" in body:
                    for record in body['Records']:
                        bucket = record["s3"]["bucket"]["name"]
                        key = record["s3"]["object"]["key"]
                        
                        # Trigger the task with clean data
                        process_s3_upload_task.delay(bucket, key)
                
                # Delete message after successful dispatch
                sqs.delete_message(
                    QueueUrl=S3_EVENTS_QUEUE, 
                    ReceiptHandle=msg['ReceiptHandle']
                )
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(5)