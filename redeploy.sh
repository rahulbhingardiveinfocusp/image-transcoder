#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="app-local"
BACKEND_IMAGE="fastapi-app:local"
BACKEND_DIR="./backend"

echo "==> Checking cluster/namespace is up (run start.sh first if not)"
kubectl get namespace "$NAMESPACE" >/dev/null 2>&1 || {
  echo "Namespace $NAMESPACE not found. Run ./start.sh first." >&2
  exit 1
}

echo "==> Rebuilding backend image into Minikube's docker daemon"
eval "$(minikube docker-env)"
docker build -t "$BACKEND_IMAGE" "$BACKEND_DIR"

echo "==> Restarting fastapi + celery to pick up the new image"
kubectl -n "$NAMESPACE" rollout restart deployment/fastapi
kubectl -n "$NAMESPACE" rollout restart deployment/celery

kubectl -n "$NAMESPACE" rollout status deployment/fastapi --timeout=120s
kubectl -n "$NAMESPACE" rollout status deployment/celery --timeout=120s

echo "==> Done. App URL: $(minikube service fastapi -n "$NAMESPACE" --url)"