#!/bin/bash
set -e

echo "🧹 Deleting resources..."
kubectl delete -f k8s/celery.yaml --ignore-not-found
kubectl delete -f k8s/fastapi.yaml --ignore-not-found
kubectl delete -f k8s/localstack.yaml --ignore-not-found
kubectl delete -f k8s/configmap.yaml --ignore-not-found
kubectl delete -f k8s/secrets.yaml --ignore-not-found

echo "🛑 Stopping Minikube..."
minikube stop

echo "✅ Done."