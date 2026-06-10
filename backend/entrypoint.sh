#!/bin/sh
set -e

if ! id celeryuser >/dev/null 2>&1; then
    echo "Creating system user for Celery compliance..."
    groupadd -g 1000 celerygroup || true
    useradd -u 1000 -g celerygroup -m celeryuser || true
fi

echo "Running database migrations..."
alembic upgrade head

echo "Starting bridge..."
python bridge.py &
BRIDGE_PID=$!

trap "kill $BRIDGE_PID" EXIT

if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.tasks.image_tasks worker --loglevel=info
else
    echo "Starting FastAPI Application..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi