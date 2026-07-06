terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "my-global-tf-state-bucket-092304627150-us-west-1-an"
    key    = "fastapi/terraform.tfstate"
    region = "us-west-1"
  }
}

# =========================================================================
# VARIABLES
# =========================================================================
variable "aws_region" {
  type    = string
  default = "us-west-1"
}
variable "s3_bucket_name"     { type = string }
variable "sqs_queue_name" {
  type    = string
  default = "image-processing-queue"
}
variable "dockerhub_username" { type = string }
variable "docker_repo"        { type = string }
variable "celery_queue_name"  { type = string }
variable "dynamo_images_table" {
  type    = string
  default = "images"
}
variable "admin_email" { type = string }
variable "admin_password" {
  type      = string
  sensitive = true
}

provider "aws" {
  region = var.aws_region
}

# =========================================================================
# 1. BACKEND STORAGE — S3, SQS
# =========================================================================
resource "aws_s3_bucket" "app_bucket" {
  bucket        = var.s3_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_cors_configuration" "app_bucket_cors" {
  bucket     = aws_s3_bucket.app_bucket.id
  depends_on = [aws_s3_bucket.app_bucket]
  cors_rule {
    allowed_origins = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "HEAD"]
    allowed_headers = ["*"]
    expose_headers  = ["ETag", "x-amz-server-side-encryption", "x-amz-request-id", "x-amz-id-2"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_public_access_block" "app_bucket_public_access" {
  bucket                  = aws_s3_bucket.app_bucket.id
  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "app_bucket_upload_policy" {
  bucket     = aws_s3_bucket.app_bucket.id
  depends_on = [aws_s3_bucket_public_access_block.app_bucket_public_access]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowPutObject"
      Effect    = "Allow"
      Principal = "*"
      Action    = "s3:PutObject"
      Resource  = "${aws_s3_bucket.app_bucket.arn}/*"
    }]
  })
}

resource "aws_sqs_queue" "app_queue" {
  name                      = var.sqs_queue_name
  receive_wait_time_seconds = 20
}

resource "aws_sqs_queue_policy" "s3_to_sqs_policy" {
  queue_url = aws_sqs_queue.app_queue.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.app_queue.arn
      Condition = { ArnEquals = { "aws:SourceArn" = aws_s3_bucket.app_bucket.arn } }
    }]
  })
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket     = aws_s3_bucket.app_bucket.id
  depends_on = [aws_sqs_queue_policy.s3_to_sqs_policy]
  queue {
    queue_arn     = aws_sqs_queue.app_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "raw/"
  }
}

resource "aws_sqs_queue" "celery_task_queue" {
  name                       = var.celery_queue_name
  visibility_timeout_seconds = 3600
  receive_wait_time_seconds  = 20
}

resource "aws_sqs_queue_policy" "celery_queue_policy" {
  queue_url  = aws_sqs_queue.celery_task_queue.url
  depends_on = [aws_iam_role.ec2_role]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = aws_iam_role.ec2_role.arn }
      Action    = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage"]
      Resource  = aws_sqs_queue.celery_task_queue.arn
    }]
  })
}

# =========================================================================
# 2. DYNAMODB
# =========================================================================
resource "aws_dynamodb_table" "images" {
  name         = var.dynamo_images_table
  billing_mode = "PAY_PER_REQUEST"

  # FIX: Python code uses single-table design with PK (hash) + SK (range).
  # The old schema used `id` as hash_key with no sort key — every get_item,
  # put_item, and update_item would have silently failed or created duplicate
  # items because the Key shape expected by boto3 is {"PK": ..., "SK": ...}.
  hash_key  = "PK"
  range_key = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  attribute {
    name = "GSI1PK"
    type = "S"
  }
  attribute {
    name = "GSI1SK"
    type = "S"
  }

  # FIX: renamed from StatusIndex → GSI1 to match index_name used in
  # dynamo_image_repo.py query_by_gsi("GSI1", ...)
  global_secondary_index {
    name            = "GSI1"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"
  }

  point_in_time_recovery { enabled = true }

  tags = {
    Environment = "dev"
    Application = "image-processor"
  }
}

# =========================================================================
# 3. IAM — EC2 ROLE & POLICY
# =========================================================================
resource "aws_iam_role" "ec2_role" {
  name_prefix = "fastapi-role-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ec2_ssm_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "ec2_policy" {
  name_prefix = "fastapi-policy-"
  role        = aws_iam_role.ec2_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:*"]
        Resource = [aws_s3_bucket.app_bucket.arn, "${aws_s3_bucket.app_bucket.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:*"]
        Resource = [aws_sqs_queue.app_queue.arn, aws_sqs_queue.celery_task_queue.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:ListQueues"]
        Resource = "*"
      },
      # FIX: DynamoDB was missing entirely. Without this the EC2 instance
      # role gets AccessDeniedException on every table operation.
      {
        Effect   = "Allow"
        Action   = ["dynamodb:*"]
        Resource = [
          aws_dynamodb_table.images.arn,
          "${aws_dynamodb_table.images.arn}/index/*",  # required for GSI queries
        ]
      },
      {
        Effect   = "Allow"
        Action   = ["cognito-idp:ListUsers", "cognito-idp:DescribeUserPool"]
        Resource = aws_cognito_user_pool.main.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name_prefix = "fastapi-prof-"
  role        = aws_iam_role.ec2_role.name
}

# =========================================================================
# 4. COMPUTE (EC2)
# =========================================================================
resource "aws_security_group" "app_sg" {
  name_prefix = "fastapi-sg-"
  description = "Allow web and API traffic"

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  lifecycle { create_before_destroy = true }
}

resource "aws_instance" "app_server" {
  ami                    = "ami-0fb110df4c5094d21"
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = "fastapi-ec2-key"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }

  user_data = <<EOF
#!/bin/bash
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Waiting for apt-get background locks to release..."
while fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1; do sleep 2; done

sudo apt-get update -y
sudo apt-get install docker.io -y
sudo systemctl start docker
sudo systemctl enable docker

sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

mkdir -p /home/ubuntu/app
cd /home/ubuntu/app

cat << 'DOCKER_COMPOSE' > docker-compose.yml
services:
  fastapi:
    image: ${var.dockerhub_username}/${var.docker_repo}:latest
    container_name: prod-fastapi
    ports:
      - "8000:8000"
    environment:
      - SQS_QUEUE_URL=${aws_sqs_queue.app_queue.url}
      - S3_BUCKET_NAME=${var.s3_bucket_name}
      - AWS_REGION=${var.aws_region}
      - ADMIN_EMAIL=${var.admin_email}
      - CONTAINER_ROLE=web
      - LOCALSTACK_ENDPOINT=
      - CELERY_QUEUE_NAME=${var.celery_queue_name}
      - CELERY_TASK_QUEUE_URL=${aws_sqs_queue.celery_task_queue.url}
      - DYNAMO_IMAGES_TABLE=${var.dynamo_images_table}
      - USER_POOL_CLIENT_ID=${aws_cognito_user_pool_client.client.id}
      - USER_POOL_ID=${aws_cognito_user_pool.main.id}
    restart: unless-stopped

  celery:
    image: ${var.dockerhub_username}/${var.docker_repo}:latest
    container_name: prod-celery
    environment:
      - SQS_QUEUE_URL=${aws_sqs_queue.app_queue.url}
      - S3_BUCKET_NAME=${var.s3_bucket_name}
      - AWS_REGION=${var.aws_region}
      - ADMIN_EMAIL=${var.admin_email}
      - CONTAINER_ROLE=worker
      - LOCALSTACK_ENDPOINT=
      - CELERY_QUEUE_NAME=${var.celery_queue_name}
      - CELERY_TASK_QUEUE_URL=${aws_sqs_queue.celery_task_queue.url}
      - DYNAMO_IMAGES_TABLE=${var.dynamo_images_table}
      - USER_POOL_CLIENT_ID=${aws_cognito_user_pool_client.client.id}
      - USER_POOL_ID=${aws_cognito_user_pool.main.id}
    restart: unless-stopped
DOCKER_COMPOSE

sleep 10
sudo /usr/local/bin/docker-compose up -d
echo "All systems running!"
EOF

  tags = { Name = "FastAPI-All-In-One-Server" }
}

# =========================================================================
# 5. FRONTEND — S3 + CLOUDFRONT
# =========================================================================
resource "aws_s3_bucket" "frontend_bucket" {
  bucket        = "${var.s3_bucket_name}-frontend"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "frontend_public_block" {
  bucket                  = aws_s3_bucket.frontend_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "frontend-oac-${var.s3_bucket_name}"
  description                       = "OAC for Angular Frontend Bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend_cdn" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"

  origin {
    domain_name              = aws_s3_bucket.frontend_bucket.bucket_regional_domain_name
    origin_id                = "S3-Frontend-Bucket"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  origin {
    domain_name = aws_instance.app_server.public_dns
    origin_id   = "EC2-Backend-API"
    custom_origin_config {
      http_port              = 8000
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  ordered_cache_behavior {
    path_pattern     = "/api/*"
    target_origin_id = "EC2-Backend-API"
    allowed_methods        = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
    cached_methods         = ["GET", "HEAD"]
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = true
      headers      = ["*"]
      cookies { forward = "all" }
    }
    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0
  }

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-Frontend-Bucket"
    viewer_protocol_policy = "redirect-to-https"
    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
    min_ttl     = 0
    default_ttl = 3600
    max_ttl     = 86400
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 10
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }
  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

resource "aws_s3_bucket_policy" "allow_cloudfront" {
  bucket = aws_s3_bucket.frontend_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "AllowCloudFrontServicePrincipalReadOnly"
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.frontend_bucket.arn}/*"
      Condition = { ArnEquals = { "aws:SourceArn" = aws_cloudfront_distribution.frontend_cdn.arn } }
    }]
  })
}

# =========================================================================
# 6. COGNITO
# =========================================================================
resource "aws_cognito_user_pool" "main" {
  name                     = "app-user-pool"
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = true
    require_uppercase = true
  }

  schema {
    attribute_data_type      = "String"
    developer_only_attribute = false
    mutable                  = true
    name                     = "email"
    required                 = true
    string_attribute_constraints {
      min_length = 7
      max_length = 256
    }
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "angular-app-client"
  user_pool_id = aws_cognito_user_pool.main.id
  explicit_auth_flows = [
    "ALLOW_USER_SRP_AUTH",
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
  ]
  prevent_user_existence_errors = "ENABLED"
  generate_secret               = false
}

resource "aws_cognito_user_group" "admin_group" {
  name         = "Admin"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Administrative users with full access"
}

resource "aws_cognito_user_group" "user_group" {
  name         = "User"
  user_pool_id = aws_cognito_user_pool.main.id
  description  = "Standard application users"
}

resource "aws_cognito_user" "admin" {
  user_pool_id = aws_cognito_user_pool.main.id
  username     = var.admin_email
  attributes = {
    email          = var.admin_email
    email_verified = "true"
  }
}

resource "aws_cognito_user_in_group" "admin_membership" {
  user_pool_id = aws_cognito_user_pool.main.id
  username     = aws_cognito_user.admin.username
  group_name   = aws_cognito_user_group.admin_group.name
}

resource "null_resource" "set_admin_password" {
  depends_on = [aws_cognito_user.admin]
  triggers   = { username = aws_cognito_user.admin.username }
  provisioner "local-exec" {
    command = <<EOT
aws cognito-idp admin-set-user-password \
  --user-pool-id ${aws_cognito_user_pool.main.id} \
  --username ${var.admin_email} \
  --password '${var.admin_password}' \
  --permanent
EOT
  }
}
# =========================================================================
# 7. LOCAL-DEV IAM USER — SCOPED TO COGNITO READ-ONLY
# =========================================================================
resource "aws_iam_user" "cognito_reader" {
  name = "cognito-readonly-local-dev"
  tags = {
    Purpose = "local-dev-cognito-readonly"
  }
}

resource "aws_iam_user_policy" "cognito_reader_policy" {
  name = "CognitoListUsersOnly"
  user = aws_iam_user.cognito_reader.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["cognito-idp:ListUsers", "cognito-idp:DescribeUserPool"]
      Resource = aws_cognito_user_pool.main.arn
    }]
  })
}

# Terraform state is the source of truth here — as long as this resource
# stays in state, `terraform apply` will NOT create a new key or rotate
# the existing one. It's only created once, the first time this resource
# is added and applied.
resource "aws_iam_access_key" "cognito_reader_key" {
  user = aws_iam_user.cognito_reader.name
}
# =========================================================================
# OUTPUTS
# =========================================================================
output "server_public_ip"     { value = aws_instance.app_server.public_ip }
output "sqs_production_url"   { value = aws_sqs_queue.app_queue.id }
output "celery_task_queue_url" { value = aws_sqs_queue.celery_task_queue.url }
output "frontend_url"         { value = "https://${aws_cloudfront_distribution.frontend_cdn.domain_name}" }
output "frontend_cdn_id"      { value = aws_cloudfront_distribution.frontend_cdn.id }
output "server_instance_id"   { value = aws_instance.app_server.id }
output "user_pool_id"         { value = aws_cognito_user_pool.main.id }
output "user_pool_client_id"  { value = aws_cognito_user_pool_client.client.id }
output "dynamo_table_name"    { value = aws_dynamodb_table.images.name }  # FIX: new output
output "cognito_reader_access_key_id" {
  value = aws_iam_access_key.cognito_reader_key.id
}
output "cognito_reader_secret_access_key" {
  value     = aws_iam_access_key.cognito_reader_key.secret
  sensitive = true
}