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
  type    = string 
}

variable "sqs_queue_name" { 
  type    = string
  default = "image-processing-queue" 
}

variable "dockerhub_username" { 
  type    = string 
}

variable "docker_repo" { 
  type    = string 
}

provider "aws" {
  region = var.aws_region
}

# =========================================================================
# 1. BACKEND STORAGE (S3) & SQS SETUP
# =========================================================================
resource "aws_s3_bucket" "app_bucket" { 
  bucket        = var.s3_bucket_name 
  force_destroy = false
}

resource "aws_s3_bucket_cors_configuration" "app_bucket_cors" {
  bucket = aws_s3_bucket.app_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = ["*"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
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
      Condition = { 
        ArnEquals = { "aws:SourceArn" = aws_s3_bucket.app_bucket.arn } 
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
# 2. FRONTEND HOSTING (S3 WITH "-frontend" SUFFIX + CLOUDFRONT CDN)
# =========================================================================

# Dedicated bucket holding your static Angular build with a clean suffix
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
  description                       = "OAC for Suffix-named Angular Frontend Bucket"
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

  default_cache_behavior {
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    target_origin_id       = "S3-Frontend-Bucket"
    viewer_protocol_policy = "allow-all"

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
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }
}

resource "aws_s3_bucket_policy" "allow_cloudfront" {
  bucket = aws_s3_bucket.frontend_bucket.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipalReadOnly"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend_bucket.arn}/*"
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudfront_distribution.frontend_cdn.arn
          }
        }
      }
    ]
  })
}

# =========================================================================
# 3. COMPUTE & FIREWALL SETUP (EC2 Host)
# =========================================================================
resource "aws_security_group" "app_sg" {
  name_prefix = "fastapi-sg-"
  description = "Allow web, api, and ssh traffic"

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

  lifecycle { 
    create_before_destroy = true 
  }
}

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
        Resource = aws_sqs_queue.app_queue.arn 
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" { 
  name_prefix = "fastapi-prof-" 
  role        = aws_iam_role.ec2_role.name 
}

resource "aws_instance" "app_server" {
  ami                    = "ami-0fb110df4c5094d21" 
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = "fastapi-ec2-key"

  user_data = <<-EOF
              #!/bin/bash
              sudo apt-get update -y
              sudo apt-get install docker.io -y
              sudo systemctl start docker
              sudo systemctl enable docker
              
              sudo docker pull ${var.dockerhub_username}/${var.docker_repo}:latest
              
              sudo docker run -d \
              --name fastapi-app \
              -p 8000:8000 \
              --restart unless-stopped \
              -e DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/postgres" \
              -e SQS_QUEUE_URL="${aws_sqs_queue.app_queue.id}" \
              -e S3_BUCKET_NAME="${var.s3_bucket_name}" \
              -e LOCALSTACK_ENDPOINT="" \
              -e ADMIN_EMAIL="yourpersonalemail@gmail.com" \
              ${var.dockerhub_username}/${var.docker_repo}:latest
              EOF

  tags = { 
    Name = "FastAPI-All-In-One-Server" 
  }
}

# =========================================================================
# OUTPUTS
# =========================================================================
output "server_public_ip" { 
  value = aws_instance.app_server.public_ip 
}

output "sqs_production_url" { 
  value = aws_sqs_queue.app_queue.id 
}

output "frontend_url" {
  value = "https://${aws_cloudfront_distribution.frontend_cdn.domain_name}"
}