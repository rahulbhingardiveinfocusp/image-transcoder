#!/usr/bin/env bash
set -euo pipefail

NAMESPACE="app-local"
REGION="us-east-1"
IDS_FILE=".local-cognito-ids"

DELETE_COGNITO=false
DELETE_MINIKUBE=false

for arg in "$@"; do
  case "$arg" in
    --with-cognito) DELETE_COGNITO=true ;;
    --with-minikube) DELETE_MINIKUBE=true ;;
    -h|--help)
      echo "Usage: ./stop.sh [--with-cognito] [--with-minikube]"
      echo "  --with-cognito   also delete the real AWS Cognito user pool created by start.sh"
      echo "  --with-minikube  also run 'minikube delete' (wipes the whole cluster)"
      exit 0
      ;;
  esac
done

echo "==> Killing any leftover localstack port-forwards"
pkill -f "port-forward.*svc/localstack" 2>/dev/null || true

echo "==> Killing persistent fastapi/frontend port-forwards"
PERSIST_PIDS_FILE=".port-forward-pids"
if [ -f "$PERSIST_PIDS_FILE" ]; then
  while read -r pid; do
    kill "$pid" 2>/dev/null || true
  done < "$PERSIST_PIDS_FILE"
  rm -f "$PERSIST_PIDS_FILE"
fi
pkill -f "port-forward.*svc/fastapi" 2>/dev/null || true
pkill -f "port-forward.*svc/frontend" 2>/dev/null || true

echo "==> Deleting app workloads (namespace: $NAMESPACE)"
kubectl delete namespace "$NAMESPACE" --ignore-not-found

if [ "$DELETE_COGNITO" = true ]; then
  if [ -f "$IDS_FILE" ]; then
    source "$IDS_FILE"
    echo "==> Deleting real Cognito user pool $USER_POOL_ID"
    aws cognito-idp delete-user-pool --user-pool-id "$USER_POOL_ID" --region "$REGION"
    rm -f "$IDS_FILE"
  else
    echo "   No $IDS_FILE found — nothing to delete in Cognito."
  fi
else
  echo "==> Skipping Cognito teardown (pass --with-cognito to delete the real user pool too)"
fi

if [ "$DELETE_MINIKUBE" = true ]; then
  echo "==> Deleting Minikube cluster entirely"
  minikube delete
else
  echo "==> Minikube cluster left running (pass --with-minikube to delete it)"
fi

echo "==> Done."