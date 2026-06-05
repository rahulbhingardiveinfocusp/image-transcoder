#!/bin/bash
set -e

# Configuration
BUCKET_NAME="my-test-bucket"
QUEUE_NAME="image-processing-queue"
EMAIL_IDENTITY="test@example.com"
REGION="us-east-1"
ACCOUNT_ID="000000000000"

echo "Initializing LocalStack resources..."

# 1. Create S3 Bucket
awslocal s3 mb s3://$BUCKET_NAME
cat <<EOF > /tmp/s3-cors.json
{
    "CORSRules": [
        {
            "AllowedHeaders": ["*"],
            "AllowedMethods": ["PUT", "POST", "GET"],
            "AllowedOrigins": ["http://localhost:4200"],
            "ExposeHeaders": ["ETag"]
        }
    ]
}
EOF
awslocal ses verify-email-identity --email-address notifications@yourdomain.com
awslocal s3api put-bucket-cors --bucket my-test-bucket --cors-configuration file:///tmp/s3-cors.json
# 2. Create SQS Queue
QUEUE_URL=$(awslocal sqs create-queue --queue-name $QUEUE_NAME --query 'QueueUrl' --output text)
QUEUE_ARN=$(awslocal sqs get-queue-attributes --queue-url $QUEUE_URL --attribute-name QueueArn --query 'Attributes.QueueArn' --output text)

# 3. SES Verification (Mock)
awslocal ses verify-email-identity --email-address $EMAIL_IDENTITY

# 4. S3 Notification to SQS
# Define the notification configuration in a temporary JSON file
cat <<EOF > /tmp/notification.json
{
  "QueueConfigurations": [
    {
      "QueueArn": "$QUEUE_ARN",
      "Events": ["s3:ObjectCreated:*"]
    }
  ]
}
EOF

# Apply the notification configuration to the bucket
awslocal s3api put-bucket-notification-configuration \
    --bucket $BUCKET_NAME \
    --notification-configuration file:///tmp/notification.json

echo "LocalStack resources initialized successfully."