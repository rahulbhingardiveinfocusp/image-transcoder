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

variable "s3_bucket_name" {
  type = string
}

variable "sqs_queue_name" {
  type    = string
  default = "image-processing-queue"
}

variable "dockerhub_username" {
  type = string
}

variable "docker_repo" {
  type = string
}

variable "ssh_public_key" {
  type        = string
  description = "SSH key for EC2 access"
}

provider "aws" {
  region = var.aws_region
}

# =========================================================================
# 1. S3 + SQS BACKEND
# =========================================================================

resource "aws_s3_bucket" "app_bucket" {
  bucket        = var.s3_bucket_name
  force_destroy = false
}

# ✅ FIXED CORS (safe, no dependency loop)
resource "aws_s3_bucket_cors_configuration" "app_bucket_cors" {
  bucket = aws_s3_bucket.app_bucket.id

  cors_rule {
    allowed_origins = ["*"]
    allowed_methods = ["GET", "PUT", "POST", "HEAD"]
    allowed_headers = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_sqs_queue" "app_queue" {
  name                      = var.sqs_queue_name
  receive_wait_time_seconds = 20
}

# FIXED SQS POLICY
resource "aws_sqs_queue_policy" "s3_to_sqs_policy" {
  queue_url = aws_sqs_queue.app_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowS3SendMessage"
      Effect = "Allow"
      Principal = {
        Service = "s3.amazonaws.com"
      }
      Action   = "sqs:SendMessage"
      Resource = aws_sqs_queue.app_queue.arn

      Condition = {
        ArnEquals = {
          "aws:SourceArn" = aws_s3_bucket.app_bucket.arn
        }
      }
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

# =========================================================================
# 2. FRONTEND (S3 + CLOUDFRONT)
# =========================================================================

resource "aws_s3_bucket" "frontend_bucket" {
  bucket        = "${var.s3_bucket_name}-frontend"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "frontend_public_block" {
  bucket = aws_s3_bucket.frontend_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "frontend-oac-${var.s3_bucket_name}"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend_cdn" {
  enabled         = true
  is_ipv6_enabled = true

  default_root_object = "index.html"

  origin {
    domain_name              = aws_s3_bucket.frontend_bucket.bucket_regional_domain_name
    origin_id                = "S3-Frontend"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  origin {
    domain_name = aws_instance.app_server.public_dns
    origin_id   = "EC2-API"

    custom_origin_config {
      http_port              = 8000
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  default_cache_behavior {
    target_origin_id       = "S3-Frontend"
    viewer_protocol_policy = "redirect-to-https"

    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods  = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }
  }

  ordered_cache_behavior {
    path_pattern     = "/images/*"
    target_origin_id = "EC2-API"

    allowed_methods = ["GET", "HEAD", "OPTIONS"]
    cached_methods  = ["GET", "HEAD"]

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

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

# FIXED CLOUDFRONT S3 POLICY (OAC compatible)
resource "aws_s3_bucket_policy" "allow_cloudfront" {
  bucket = aws_s3_bucket.frontend_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "AllowCloudFrontRead"
      Effect = "Allow"

      Principal = {
        Service = "cloudfront.amazonaws.com"
      }

      Action   = "s3:GetObject"
      Resource = "${aws_s3_bucket.frontend_bucket.arn}/*"

      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.frontend_cdn.arn
        }
      }
    }]
  })
}

# =========================================================================
# 3. EC2
# =========================================================================

resource "aws_security_group" "app_sg" {
  name_prefix = "fastapi-sg-"

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

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
}

resource "aws_iam_role" "ec2_role" {
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "ec2_policy" {
  role = aws_iam_role.ec2_role.id

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
        Resource = aws_sqs_queue.app_queue.arn
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "app_server" {
  ami                    = "ami-0fb110df4c5094d21"
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  metadata_options {
    http_endpoint = "enabled"
    http_tokens   = "required"
  }

  user_data = <<EOF
#!/bin/bash
set -e

apt-get update -y
apt-get install -y docker.io
systemctl enable docker
systemctl start docker

curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

mkdir -p /home/ubuntu/app
cd /home/ubuntu/app

cat << 'EOF2' > docker-compose.yml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: prod-postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: fastapi
    ports:
      - "5432:5432"

  fastapi:
    image: ${var.dockerhub_username}/${var.docker_repo}:latest
    container_name: prod-fastapi
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/fastapi
      SQS_QUEUE_URL: ${aws_sqs_queue.app_queue.url}
      S3_BUCKET_NAME: ${var.s3_bucket_name}
      AWS_REGION: ${var.aws_region}
      CONTAINER_ROLE: web
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    restart: always

  celery:
    image: ${var.dockerhub_username}/${var.docker_repo}:latest
    container_name: prod-celery
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/fastapi
      SQS_QUEUE_URL: ${aws_sqs_queue.app_queue.url}
      S3_BUCKET_NAME: ${var.s3_bucket_name}
      AWS_REGION: ${var.aws_region}
      CONTAINER_ROLE: worker
    depends_on:
      - postgres
    restart: always
EOF2

docker-compose up -d
EOF
}

# =========================================================================
# OUTPUTS
# =========================================================================

output "server_public_ip" {
  value = aws_instance.app_server.public_ip
}

output "frontend_url" {
  value = "https://${aws_cloudfront_distribution.frontend_cdn.domain_name}"
}

output "sqs_url" {
  value = aws_sqs_queue.app_queue.url
}