#!/bin/bash
set -e

echo "🚀 Ensuring Minikube is running..."
if ! minikube status &>/dev/null; then
  minikube start --alsologtostderr -v=1
else
  echo "✅ Minikube already running."
fi

echo "🧹 Clearing previous app resources and data..."
kubectl delete -f k8s/ --ignore-not-found
kubectl delete -f k8s/localstack-init-configmap.yaml --ignore-not-found
kubectl delete pvc --all --ignore-not-found

echo "📦 Building fresh FastAPI/Celery image inside Minikube..."
minikube image build -t it-fastapi:local ./backend

echo "📦 Applying Kubernetes manifests..."
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/localstack-init-configmap.yaml
kubectl apply -f k8s/localstack.yaml

echo "⏳ Waiting for LocalStack pod to be ready..."
kubectl wait --for=condition=ready pod -l app=localstack --timeout=180s

echo "⏳ Waiting for LocalStack init script to finish (queue/bucket/table creation)..."
LOCALSTACK_POD=$(kubectl get pod -l app=localstack -o jsonpath='{.items[0].metadata.name}')
until kubectl logs "$LOCALSTACK_POD" 2>/dev/null | grep -q "LocalStack init complete."; do
  echo "  still initializing..."
  sleep 2
done
echo "✅ LocalStack init script finished."

echo "📦 Applying FastAPI/Celery manifests..."
kubectl apply -f k8s/fastapi.yaml
kubectl apply -f k8s/celery.yaml

echo "⏳ Waiting for pods..."
kubectl wait --for=condition=ready pod -l app=fastapi --timeout=180s
kubectl wait --for=condition=ready pod -l app=celery --timeout=180s

echo "🌐 Starting port-forwards..."
kubectl port-forward service/fastapi 8000:8000 &
FASTAPI_PF_PID=$!
kubectl port-forward service/localstack 4566:4566 &
LOCALSTACK_PF_PID=$!

echo "✅ Port-forwards running (fastapi PID $FASTAPI_PF_PID, localstack PID $LOCALSTACK_PF_PID)."
echo "Press Ctrl+C to stop both."

# Clean up both background port-forwards when the script is interrupted
trap "kill $FASTAPI_PF_PID $LOCALSTACK_PF_PID 2>/dev/null" EXIT

wait