#!/bin/bash
set -e

# Configuration
BUCKET_NAME="my-test-bucket"
QUEUE_NAME="image-processing-queue"
CELERY_QUEUE_NAME="simple-celery-queue"
EMAIL_IDENTITY="test@example.com"
REGION="us-west-1"
ACCOUNT_ID="000000000000"
DYNAMO_TABLE="images"

echo "Initializing LocalStack resources..."

# 1. Create S3 Bucket
awslocal s3 mb s3://$BUCKET_NAME

cat <<EOF > /tmp/s3-cors.json
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["PUT", "POST", "GET"],
            "AllowedHeaders": ["*"],
            "AllowedOrigins": ["*"],
            "ExposeHeaders": ["ETag"]
        }
    ]
}
EOF
awslocal s3api put-bucket-cors --bucket $BUCKET_NAME --cors-configuration file:///tmp/s3-cors.json

# 2. SES Verification
awslocal ses verify-email-identity --email-address $EMAIL_IDENTITY
awslocal ses verify-email-identity --email-address notifications@yourdomain.com

# 3. Create S3 events SQS queue
QUEUE_URL=$(awslocal sqs create-queue --queue-name $QUEUE_NAME --query 'QueueUrl' --output text)
QUEUE_ARN=$(awslocal sqs get-queue-attributes \
    --queue-url $QUEUE_URL \
    --attribute-name QueueArn \
    --query 'Attributes.QueueArn' \
    --output text)

# 4. Create Celery task queue (was missing — settings.CELERY_TASK_QUEUE_URL references this)
awslocal sqs create-queue \
    --queue-name $CELERY_QUEUE_NAME \
    --attributes VisibilityTimeout=3600

# 5. S3 → SQS notification (raw/ prefix only)
cat <<EOF > /tmp/notification.json
{
  "QueueConfigurations": [
    {
      "QueueArn": "$QUEUE_ARN",
      "Events": ["s3:ObjectCreated:*"],
      "Filter": {
        "Key": {
          "FilterRules": [
            {"Name": "prefix", "Value": "raw/"}
          ]
        }
      }
    }
  ]
}
EOF

awslocal s3api put-bucket-notification-configuration \
    --bucket $BUCKET_NAME \
    --notification-configuration file:///tmp/notification.json

# 6. Create DynamoDB table (was missing entirely)
awslocal dynamodb create-table \
    --table-name $DYNAMO_TABLE \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
        AttributeName=GSI1PK,AttributeType=S \
        AttributeName=GSI1SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --billing-mode PAY_PER_REQUEST \
    --global-secondary-indexes '[
      {
        "IndexName": "GSI1",
        "KeySchema": [
          {"AttributeName": "GSI1PK", "KeyType": "HASH"},
          {"AttributeName": "GSI1SK", "KeyType": "RANGE"}
        ],
        "Projection": {"ProjectionType": "ALL"}
      }
    ]'

echo "LocalStack resources initialized successfully."
echo "  S3 bucket   : $BUCKET_NAME"
echo "  SQS (S3)    : $QUEUE_URL"
echo "  SQS (Celery): $CELERY_QUEUE_NAME"
echo "  DynamoDB    : $DYNAMO_TABLE"
touch /var/lib/localstack/init-complete
echo "Init complete"