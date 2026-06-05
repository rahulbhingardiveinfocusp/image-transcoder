# Image Processing System

This project provides an event-driven asynchronous image processing pipeline. When a user requests an upload, the backend manages the S3 workflow, uses an SQS queue to trigger background processing via Celery, and finally handles image resizing and email notification.



---

## 1. System Components
* **FastAPI**: Handles user requests and generates S3 upload URLs.
* **LocalStack**: Mocks AWS services (S3, SQS, SES) locally.
* **SQS (Simple Queue Service)**: Buffers S3 events so the backend can process them reliably.
* **Bridge (`bridge.py`)**: A worker process that listens to SQS and dispatches Celery tasks.
* **Celery Worker**: Performs heavy-lifting (image resizing) asynchronously.
* **Pillow**: Python library for image resizing.

---

## 2. Prerequisites
* Python 3.10+
* Docker Desktop (running for LocalStack)
* PostgreSQL
* Dependencies: `pip install -r requirements.txt` (ensure `pillow`, `celery`, `boto3`, `fastapi`, `sqlalchemy` are included).

---

## 3. How to Run Everything

You need to run four components simultaneously in different terminal windows.

### Step 1: Start LocalStack
Ensure Docker is running, then start LocalStack:
```bash
docker compose up -d

in another terminal
celery -A app.tasks.image_tasks worker --loglevel=info -P gevent

and another temninal 
python bridge.py

finally
uvicorn app.main:app --reload


4. Operational Workflow
Request Upload: Call the POST /images/request-upload endpoint. You will receive a presigned S3 URL.

Upload: Upload your image to the provided S3 URL.

Automatic Trigger:

S3 detects the upload and sends a message to the SQS queue.

bridge.py detects the message and triggers the Celery task.

Celery downloads the image, resizes it using Pillow, uploads the result to processed/ in S3, and emails the user.

Verification: Check your terminal logs to see the processing status and check http://localhost:4566/_localstack/ to browse the S3 bucket files.

5. Troubleshooting
Imports not found? Ensure your PYTHONPATH includes the backend/ root directory.

No Events? Check if you have run the put-bucket-notification-configuration command to link S3 to SQS.

Worker not responding? Ensure Celery is connected to your Redis/Broker URL.