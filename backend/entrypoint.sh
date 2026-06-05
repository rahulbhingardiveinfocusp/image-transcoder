#!/bin/sh
set -e

echo "Running database migrations..."
# This applies all pending migrations to the database
alembic upgrade head

echo "Starting FastAPI in ${ENV_NAME:-local} mode..."
# Start FastAPI in the background
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &

# Start the bridge
echo "Starting bridge..."
python bridge.py
celery -A app.tasks.image_tasks worker --loglevel=info -P gevent