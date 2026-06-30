#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# CONFIG — adjust as needed
# =============================================================================
NAMESPACE="app-local"
REGION="us-east-1"
S3_BUCKET="local-image-bucket"
SQS_QUEUE="image-processing-queue"
CELERY_QUEUE="celery-task-queue"
DYNAMO_TABLE="images"
ADMIN_EMAIL="${ADMIN_EMAIL:-admin@example.com}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-LocalDevPass1!}"
BACKEND_IMAGE="fastapi-app:local"
BACKEND_DIR="./backend"
ENDPOINT="http://localhost:4566"
IDS_FILE=".local-cognito-ids"   # caches pool/client id between runs (idempotency)

# Fake creds used ONLY for LocalStack calls (S3/SQS/DynamoDB). Real AWS calls
# (Cognito fallback) below explicitly avoid these so your normal profile is used.
LS_ENV=(env AWS_ACCESS_KEY_ID=test AWS_SECRET_ACCESS_KEY=test AWS_DEFAULT_REGION="$REGION")

PF_PID=""
cleanup() {
  if [ -n "$PF_PID" ]; then kill "$PF_PID" 2>/dev/null || true; fi
}
trap cleanup EXIT

echo "==> 1. Minikube"
if ! minikube status >/dev/null 2>&1; then
  minikube start --cpus=4 --memory=6g
fi

echo "==> 2. Build backend image into Minikube's docker daemon"
eval "$(minikube docker-env)"
docker build -t "$BACKEND_IMAGE" "$BACKEND_DIR"

echo "==> 3. Apply namespace + LocalStack"
kubectl apply -f k8s/namespace.yaml
export LOCALSTACK_AUTH_TOKEN="${LOCALSTACK_AUTH_TOKEN:-}"
envsubst < k8s/localstack.yaml > /tmp/localstack.yaml
kubectl apply -f /tmp/localstack.yaml
kubectl -n "$NAMESPACE" wait --for=condition=ready pod -l app=localstack --timeout=180s

echo "==> 4. Port-forward LocalStack to host so this script can provision it"
kubectl -n "$NAMESPACE" port-forward svc/localstack 4566:4566 >/tmp/localstack-pf.log 2>&1 &
PF_PID=$!
sleep 3

echo "==> 5. Create S3 bucket"
"${LS_ENV[@]}" aws --endpoint-url="$ENDPOINT" s3 mb "s3://$S3_BUCKET" 2>/dev/null || echo "   (bucket already exists)"

echo "==> 6. Create SQS queues"
SQS_QUEUE_URL=$("${LS_ENV[@]}" aws --endpoint-url="$ENDPOINT" sqs create-queue \
  --queue-name "$SQS_QUEUE" --attributes ReceiveMessageWaitTimeSeconds=20 \
  --query QueueUrl --output text)

CELERY_QUEUE_URL=$("${LS_ENV[@]}" aws --endpoint-url="$ENDPOINT" sqs create-queue \
  --queue-name "$CELERY_QUEUE" --attributes VisibilityTimeout=3600,ReceiveMessageWaitTimeSeconds=20 \
  --query QueueUrl --output text)

echo "==> 7. Wire S3 -> SQS notifications"
SQS_QUEUE_ARN=$("${LS_ENV[@]}" aws --endpoint-url="$ENDPOINT" sqs get-queue-attributes \
  --queue-url "$SQS_QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)

cat > /tmp/notif.json <<EOF
{
  "QueueConfigurations": [
    {
      "QueueArn": "$SQS_QUEUE_ARN",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {"Key": {"FilterRules": [{"Name": "prefix", "Value": "raw/"}]}}
    }
  ]
}
EOF
"${LS_ENV[@]}" aws --endpoint-url="$ENDPOINT" s3api put-bucket-notification-configuration \
  --bucket "$S3_BUCKET" --notification-configuration file:///tmp/notif.json

echo "==> 8. Create DynamoDB table (PK/SK + GSI1, matches single-table design)"
"${LS_ENV[@]}" aws --endpoint-url="$ENDPOINT" dynamodb create-table \
  --table-name "$DYNAMO_TABLE" \
  --attribute-definitions \
      AttributeName=PK,AttributeType=S \
      AttributeName=SK,AttributeType=S \
      AttributeName=GSI1PK,AttributeType=S \
      AttributeName=GSI1SK,AttributeType=S \
  --key-schema AttributeName=PK,KeyType=HASH AttributeName=SK,KeyType=RANGE \
  --global-secondary-indexes '[{
      "IndexName": "GSI1",
      "KeySchema": [
        {"AttributeName":"GSI1PK","KeyType":"HASH"},
        {"AttributeName":"GSI1SK","KeyType":"RANGE"}
      ],
      "Projection": {"ProjectionType":"ALL"}
  }]' \
  --billing-mode PAY_PER_REQUEST >/dev/null 2>&1 || echo "   (table already exists)"

echo "==> 9. Cognito"
if [ -n "${USER_POOL_ID:-}" ] && [ -n "${USER_POOL_CLIENT_ID:-}" ]; then
  # Pre-provisioned via the GitHub Actions "cognito-only" workflow_dispatch
  # option — no real AWS credentials needed locally at all in this path.
  echo "   Using pre-set USER_POOL_ID/USER_POOL_CLIENT_ID from environment (from CI)"
  cat > "$IDS_FILE" <<EOF
USER_POOL_ID=$USER_POOL_ID
USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID
EOF
elif [ -f "$IDS_FILE" ]; then
  source "$IDS_FILE"
  echo "   Reusing cached pool: $USER_POOL_ID"
else
  echo "   No USER_POOL_ID/USER_POOL_CLIENT_ID set and no cache found."
  echo "   Falling back to creating Cognito via your local AWS CLI profile (real AWS)."
  USER_POOL_ID=$(aws cognito-idp create-user-pool \
    --pool-name "app-user-pool-local" \
    --region "$REGION" \
    --username-attributes email \
    --auto-verified-attributes email \
    --policies '{"PasswordPolicy":{"MinimumLength":8,"RequireUppercase":true,"RequireLowercase":true,"RequireNumbers":true,"RequireSymbols":true}}' \
    --query 'UserPool.Id' --output text)

  USER_POOL_CLIENT_ID=$(aws cognito-idp create-user-pool-client \
    --user-pool-id "$USER_POOL_ID" \
    --region "$REGION" \
    --client-name "angular-app-client-local" \
    --explicit-auth-flows ALLOW_USER_SRP_AUTH ALLOW_USER_PASSWORD_AUTH ALLOW_REFRESH_TOKEN_AUTH \
    --prevent-user-existence-errors ENABLED \
    --no-generate-secret \
    --query 'UserPoolClient.ClientId' --output text)

  aws cognito-idp create-group --user-pool-id "$USER_POOL_ID" --region "$REGION" \
    --group-name Admin --description "Administrative users with full access" >/dev/null
  aws cognito-idp create-group --user-pool-id "$USER_POOL_ID" --region "$REGION" \
    --group-name User --description "Standard application users" >/dev/null

  aws cognito-idp admin-create-user --user-pool-id "$USER_POOL_ID" --region "$REGION" \
    --username "$ADMIN_EMAIL" \
    --user-attributes Name=email,Value="$ADMIN_EMAIL" Name=email_verified,Value=true \
    --message-action SUPPRESS >/dev/null

  aws cognito-idp admin-set-user-password --user-pool-id "$USER_POOL_ID" --region "$REGION" \
    --username "$ADMIN_EMAIL" --password "$ADMIN_PASSWORD" --permanent

  aws cognito-idp admin-add-user-to-group --user-pool-id "$USER_POOL_ID" --region "$REGION" \
    --username "$ADMIN_EMAIL" --group-name Admin

  cat > "$IDS_FILE" <<EOF
USER_POOL_ID=$USER_POOL_ID
USER_POOL_CLIENT_ID=$USER_POOL_CLIENT_ID
EOF
  echo "   Created pool: $USER_POOL_ID (admin: $ADMIN_EMAIL / $ADMIN_PASSWORD)"
fi

echo "==> 10. Render ConfigMap and deploy app"
export S3_BUCKET SQS_QUEUE_URL CELERY_QUEUE CELERY_QUEUE_URL DYNAMO_TABLE REGION ADMIN_EMAIL USER_POOL_ID USER_POOL_CLIENT_ID
envsubst < k8s/configmap.yaml > /tmp/configmap.yaml
kubectl apply -f /tmp/configmap.yaml
kubectl apply -f k8s/fastapi.yaml
kubectl apply -f k8s/celery.yaml

kubectl -n "$NAMESPACE" rollout status deployment/fastapi --timeout=120s
kubectl -n "$NAMESPACE" rollout status deployment/celery --timeout=120s

echo "==> Done."
echo "    App URL:   $(minikube service fastapi -n "$NAMESPACE" --url)"
echo "    Admin login: $ADMIN_EMAIL / $ADMIN_PASSWORD"
echo "    LocalStack: kubectl -n $NAMESPACE port-forward svc/localstack 4566:4566 (if you need host access again)"