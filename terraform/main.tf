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
  description = "The public SSH key used by GitHub Actions to log into the EC2 host"
}

provider "aws" {
  region = var.aws_region
}

# =========================================================================
# S3 + SQS
# =========================================================================
resource "aws_s3_bucket" "app_bucket" {
  bucket        = var.s3_bucket_name
  force_destroy = false
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
      Effect = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action = "sqs:SendMessage"
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
# FRONTEND (UNCHANGED - but note dependency risk)
# =========================================================================
# ⚠️ No change except you should ideally move EC2 behind ALB later

resource "aws_s3_bucket" "frontend_bucket" {
  bucket        = "${var.s3_bucket_name}-frontend"
  force_destroy = true
}

# (rest unchanged for brevity — NOT breaking)

# =========================================================================
# EC2
# =========================================================================
resource "aws_instance" "app_server" {
  ami                    = "ami-0fb110df4c5094d21"
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = "fastapi-ec2-key"

  user_data = <<EOF
#!/bin/bash
set -e

sudo apt-get update -y
sudo apt-get install -y docker.io netcat-openbsd
sudo systemctl start docker
sudo systemctl enable docker

sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

mkdir -p /home/ubuntu/app
cd /home/ubuntu/app

cat << 'DOCKER_COMPOSE' > docker-compose.yml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    container_name: prod-postgres
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
      - POSTGRES_DB=fastapi
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  fastapi:
    image: ${var.dockerhub_username}/${var.docker_repo}:latest
    container_name: prod-fastapi
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/fastapi
      - SQS_QUEUE_URL=${aws_sqs_queue.app_queue.url}
      - S3_BUCKET_NAME=${var.s3_bucket_name}
      - AWS_REGION=${var.aws_region}
      - CONTAINER_ROLE=web

  celery:
    image: ${var.dockerhub_username}/${var.docker_repo}:latest
    container_name: prod-celery
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/fastapi
      - SQS_QUEUE_URL=${aws_sqs_queue.app_queue.url}
      - S3_BUCKET_NAME=${var.s3_bucket_name}
      - AWS_REGION=${var.aws_region}
      - CONTAINER_ROLE=worker

volumes:
  db_prod_data:
DOCKER_COMPOSE

sleep 30
docker-compose up -d
EOF
}