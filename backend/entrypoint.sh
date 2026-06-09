#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

# 🟢 Runs for BOTH containers so credentials/mappings are handled
echo "Starting bridge..."
python bridge.py &

# 🟢 Route execution based on the container's designated role
if [ "$CONTAINER_ROLE" = "worker" ]; then
    echo "Starting Celery worker..."
    exec celery -A app.tasks.image_tasks worker --loglevel=info -P gevent --uid=1000
else
    echo "Starting FastAPI Application..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi