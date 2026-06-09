#!/bin/sh
set -e

# 🟢 FIX: Ensure UID 1000 exists inside this container's Linux system
if ! getent passwd 1000 > /dev/null 2>&1; then
    echo "Creating system user for Celery compliance..."
    # Creates a group and user with ID 1000 so getpwuid(1000) will succeed
    addgroup -g 1000 celerygroup && adduser -u 1000 -G celerygroup -D celeryuser
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting bridge..."
python bridge.py &

if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.tasks.image_tasks worker --loglevel=info -P gevent
else
    echo "Starting FastAPI Application..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi