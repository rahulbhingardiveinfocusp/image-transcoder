terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "my-global-tf-state-bucket" 
    key    = "fastapi/terraform.tfstate"
    region = "us-west-1"
  }
}

# =========================================================================
# VARIABLES
# =========================================================================
variable "aws_region" { type = string; default = "us-west-1" }
variable "s3_bucket_name" { type = string }
variable "sqs_queue_name" { type = string; default = "image-processing-queue" }

# NEW: Variables so the EC2 instance knows which Docker image to pull
variable "dockerhub_username" { type = string }
variable "docker_repo" { type = string }

provider "aws" {
  region = var.aws_region
}

# (S3, SQS, Security Groups, and IAM Roles stay exactly the same as before...)
resource "aws_s3_bucket" "app_bucket" { bucket = var.s3_bucket_name }
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
resource "aws_sqs_queue" "app_queue" { name = var.sqs_queue_name }
resource "aws_sqs_queue_policy" "s3_to_sqs_policy" {
  queue_url = aws_sqs_queue.app_queue.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action = "sqs:SendMessage"
      Resource = aws_sqs_queue.app_queue.arn
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
resource "aws_security_group" "app_sg" {
  name_prefix = "fastapi-sg-"
  ingress { from_port = 22; to_port = 22; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 80; to_port = 80; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 8000; to_port = 8000; protocol = "tcp"; cidr_blocks = ["0.0.0.0/0"] }
  egress { from_port = 0; to_port = 0; protocol = "-1"; cidr_blocks = ["0.0.0.0/0"] }
  lifecycle { create_before_destroy = true }
}
resource "aws_iam_role" "ec2_role" {
  name_prefix = "fastapi-role-"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole"; Effect = "Allow"; Principal = { Service = "ec2.amazonaws.com" } }]
  })
}
resource "aws_iam_role_policy" "ec2_policy" {
  name_prefix = "fastapi-policy-"
  role        = aws_iam_role.ec2_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow"; Action = ["s3:*"]; Resource = [aws_s3_bucket.app_bucket.arn, "${aws_s3_bucket.app_bucket.arn}/*"] },
      { Effect = "Allow"; Action = ["sqs:*"]; Resource = aws_sqs_queue.app_queue.arn }
    ]
  })
}
resource "aws_iam_instance_profile" "ec2_profile" { name_prefix = "fastapi-prof-"; role = aws_iam_role.ec2_role.name }

# =========================================================================
# 4. EC2 HOST WITH AUTO-PULL USER DATA
# =========================================================================
resource "aws_instance" "app_server" {
  ami                    = "ami-0fb110df4c5094d21" 
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = "fastapi-ec2-key"

  # FIXED: User data now automatically pulls and runs your Docker container on startup
  user_data = <<-EOF
              #!/bin/bash
              sudo apt-get update -y
              sudo apt-get install docker.io -y
              sudo systemctl start docker
              sudo systemctl enable docker
              
              # Pull the latest image directly from Docker Hub without needing SSH
              sudo docker pull ${var.dockerhub_username}/${var.docker_repo}:latest
              
              # Run the container
              sudo docker run -d \
                --name fastapi-app \
                -p 8000:8000 \
                --restart always \
                ${var.dockerhub_username}/${var.docker_repo}:latest
              EOF

  tags = { Name = "FastAPI-All-In-One-Server" }
}

output "server_public_ip" { value = aws_instance.app_server.public_ip }
output "sqs_production_url" { value = aws_sqs_queue.app_queue.id }