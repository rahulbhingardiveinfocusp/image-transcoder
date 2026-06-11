#!/bin/sh
set -e

log() {
    echo "[ENTRYPOINT] $1"
}

fail() {
    echo "[ENTRYPOINT][FATAL] $1"
    exit 1
}

# -------------------------------------------------
# Create celery user
# -------------------------------------------------
if ! id celeryuser >/dev/null 2>&1; then
    log "Creating system user for Celery compliance..."
    groupadd -g 1000 celerygroup || true
    useradd -u 1000 -g celerygroup -m celeryuser || true
fi

# -------------------------------------------------
# Wait for Postgres
# -------------------------------------------------
log "Waiting for Postgres..."

command -v nc >/dev/null 2>&1 || fail "netcat (nc) not installed in image"

for i in $(seq 1 30); do
    nc -z postgres 5432 && break
    log "Postgres not ready... retry $i/30"
    sleep 2
done

nc -z postgres 5432 || fail "Postgres unreachable after retries"

log "Postgres is ready"

# -------------------------------------------------
# Migrations
# -------------------------------------------------
log "Running database migrations..."
if ! alembic upgrade head; then
    fail "Alembic migrations failed"
fi

# -------------------------------------------------
# Bridge process
# -------------------------------------------------
log "Starting bridge..."
python bridge.py > /proc/1/fd/1 2>&1 &
BRIDGE_PID=$!

sleep 2

if ! kill -0 $BRIDGE_PID 2>/dev/null; then
    log "bridge.py failed at startup"
    log "Check logs above for root cause"
else
    log "bridge.py started successfully (PID $BRIDGE_PID)"
fi

cleanup() {
    log "Stopping bridge..."
    kill -TERM "$BRIDGE_PID" 2>/dev/null || true
    wait "$BRIDGE_PID" 2>/dev/null || true
}

trap cleanup INT TERM EXIT

# -------------------------------------------------
# Main process
# -------------------------------------------------
if [ "$CONTAINER_ROLE" = "worker" ]; then
    log "Starting Celery worker..."
    exec celery -A app.tasks.image_tasks worker --loglevel=info
else
    log "Starting FastAPI..."
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi