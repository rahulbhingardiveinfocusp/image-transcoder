# #!/bin/sh
# set -e

# echo "Running database migrations..."
# # This applies all pending migrations to the database
# alembic upgrade head

# echo "Starting FastAPI in ${ENV_NAME:-local} mode..."
# # Start FastAPI in the background
# uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# # Start the bridge
# echo "Starting bridge..."
# python bridge.py
# celery -A app.tasks.image_tasks worker --loglevel=info -P gevent

#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

# 🟢 1. Start the bridge in the BACKGROUND using '&'
echo "Starting bridge..."
python bridge.py &

# 🟢 2. Start Celery in the BACKGROUND using '&'
echo "Starting Celery worker..."
celery -A app.tasks.image_tasks worker --loglevel=info -P gevent &

# 🟢 3. Run Uvicorn in the FOREGROUND as the main process using 'exec'
# Removing the trailing '&' keeps the Docker container alive on Port 8000!
echo "Starting FastAPI Application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000