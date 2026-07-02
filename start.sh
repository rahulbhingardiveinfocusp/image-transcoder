#!/bin/bash
set -e

echo "🚀 Starting Minikube..."
minikube start

echo "📦 Building FastAPI/Celery image..."
minikube image build -t it-fastapi:local ./backend

echo "📦 Applying Kubernetes manifests..."
kubectl apply -f k8s/secrets.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/localstack.yaml
kubectl apply -f k8s/fastapi.yaml
kubectl apply -f k8s/celery.yaml

echo "⏳ Waiting for pods..."
kubectl wait --for=condition=ready pod -l app=localstack --timeout=180s
kubectl wait --for=condition=ready pod -l app=fastapi --timeout=180s
kubectl wait --for=condition=ready pod -l app=celery --timeout=180s

echo "🌐 Starting port-forward..."
kubectl port-forward service/fastapi 8000:8000