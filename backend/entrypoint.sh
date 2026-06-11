#!/bin/sh
set -e

echo "Starting service..."

if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.tasks.image_tasks worker --loglevel=info
else
    echo "Starting FastAPI..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi