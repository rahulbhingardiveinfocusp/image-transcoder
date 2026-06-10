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

cleanup() {
    echo "Stopping bridge..."
    kill -TERM "$BRIDGE_PID" 2>/dev/null || true
    wait "$BRIDGE_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

sleep 2
if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    echo "bridge.py failed to start"
    exit 1
fi

if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.tasks.image_tasks worker --loglevel=info
else
    echo "Starting FastAPI Application..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi