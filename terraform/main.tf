terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# =========================================================================
# VARIABLES (Passed dynamically from GitHub Environment Secrets)
# =========================================================================
variable "aws_region" {
  type    = string
  default = "us-west-1" 
}

variable "s3_bucket_name" {
  type        = string
  description = "The globally unique bucket name matching your secret/env configuration"
}

variable "sqs_queue_name" {
  type        = string
  default     = "image-processing-queue"
  description = "The queue name matching your secret/env configuration"
}

provider "aws" {
  region = var.aws_region
}

# =========================================================================
# 1. STORAGE (S3) & CORS SETUP
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

# =========================================================================
# 2. QUEUE (SQS) & PERMISSIONS SETUP
# =========================================================================
resource "aws_sqs_queue" "app_queue" {
  name                      = var.sqs_queue_name
  receive_wait_time_seconds = 20 
}

resource "aws_sqs_queue_policy" "s3_to_sqs_policy" {
  queue_url = aws_sqs_queue.app_queue.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "s3.amazonaws.com" }
        Action    = "sqs:SendMessage"
        Resource  = aws_sqs_queue.app_queue.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_s3_bucket.app_bucket.arn
          }
        }
      }
    ]
  })
}

# =========================================================================
# 3. AUTOMATION (S3 Event Notification Trigger)
# =========================================================================
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
# 4. COMPUTE & FIREWALL SETUP (EC2 Host)
# =========================================================================
resource "aws_security_group" "app_sg" {
  # FIXED: Converted to name_prefix to prevent any future group replication blocks
  name_prefix = "${var.s3_bucket_name}-sg-" 
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
  # FIXED: Converted 'name' to 'name_prefix' to side-step the 409 error completely
  name_prefix = "${var.s3_bucket_name}-ec2-role-" 

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
  # FIXED: Converted to name_prefix
  name_prefix = "${var.s3_bucket_name}-ec2-policy-"
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
  # FIXED: Converted to name_prefix
  name_prefix = "${var.s3_bucket_name}-ec2-profile-"
  role        = aws_iam_role.ec2_role.name
}

resource "aws_instance" "app_server" {
  ami                    = "ami-05c06ad93fe4c5413" # Verified Ubuntu 24.04 LTS for us-west-1
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.app_sg.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name

  user_data = <<-EOF
              #!/bin/bash
              sudo apt-get update -y
              sudo apt-get install docker.io docker-compose -y
              sudo systemctl start docker
              sudo systemctl enable docker
              mkdir -p /home/ubuntu/app
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