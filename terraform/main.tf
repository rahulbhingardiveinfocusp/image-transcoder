terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# =========================================================================
# 1. STORAGE (S3) & CORS SETUP
# =========================================================================
resource "aws_s3_bucket" "app_bucket" {
  bucket        = "my-test-bucket" 
  force_destroy = true 
}

# Translates your 'put-bucket-cors' command to AWS Production
resource "aws_s3_bucket_cors_configuration" "app_bucket_cors" {
  bucket = aws_s3_bucket.app_bucket.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "POST", "GET"]
    allowed_origins = ["*"] # Allows any browser across the internet to stream uploads
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

# =========================================================================
# 2. QUEUE (SQS) & PERMISSIONS SETUP
# =========================================================================
resource "aws_sqs_queue" "app_queue" {
  name = "image-processing-queue"
}

# CRITICAL FOR REAL AWS: Allows S3 bucket permission to push events into your SQS Queue
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
# 3. AUTOMATION (S3 Event Event Notification Trigger)
# =========================================================================
# Translates your '/tmp/notification.json' logic into AWS production
resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket     = aws_s3_bucket.app_bucket.id
  depends_on = [aws_sqs_queue_policy.s3_to_sqs_policy] # SQS must be open to listening before connecting

  queue {
    queue_arn     = aws_sqs_queue.app_queue.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "raw/" # Matches your script exactly
  }
}

# =========================================================================
# 4. COMPUTE & FIREWALL SETUP (EC2 Host)
# =========================================================================
resource "aws_security_group" "app_sg" {
  name        = "fastapi-security-group"
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
    cidr_blocks = ["0.0.0.0/0"] # Angular Web Access
  }

  ingress {
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"] # FastAPI direct api communication
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# IAM Role so EC2 doesn't need hardcoded AWS Keys
resource "aws_iam_role" "ec2_role" {
  name = "fastapi_ec2_role"

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
  name = "fastapi_ec2_policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:*"]
        Resource = ["${aws_s3_bucket.app_bucket.arn}", "${aws_s3_bucket.app_bucket.arn}/*"]
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:*"]
        Resource = "${aws_sqs_queue.app_queue.arn}"
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "fastapi_ec2_profile"
  role = aws_iam_role.ec2_role.name
}

resource "aws_instance" "app_server" {
  ami                    = "ami-0c7217cdde317cfec" # Ubuntu 22.04 LTS
  instance_type          = "t2.micro"
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

output "server_public_ip" {
  value = aws_instance.app_server.public_ip
}