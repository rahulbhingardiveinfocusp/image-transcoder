#!/bin/sh
set -e

# Create system user if missing
if ! getent passwd 1000 > /dev/null 2>&1; then
    echo "Creating system user for Celery compliance..."
    addgroup -g 1000 celerygroup
    adduser -u 1000 -G celerygroup celeryuser
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting bridge..."
python bridge.py &

if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec su-exec celeryuser celery -A app.tasks.image_tasks worker --loglevel=info
else
    echo "Starting FastAPI Application..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi