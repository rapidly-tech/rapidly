# Rapidly infrastructure — application access module
# Configures IAM policies granting the Rapidly backend access to S3 buckets
terraform {
  required_version = ">= 1.2"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

variable "username" {
  description = "Name of the IAM user to attach policies to"
  type        = string
}

variable "buckets" {
  description = "Bucket names and policy descriptions"
  type = object({
    files        = object({ name = string, description = optional(string) })
    public_files = object({ name = string, description = optional(string) })
  })
}

data "aws_iam_policy_document" "files" {
  statement {
    sid = "VisualEditor0"
    actions = [
      "s3:PutObject",
      "s3:GetObjectAttributes",
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:GetObjectVersionAttributes",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
    ]
    resources = ["arn:aws:s3:::${var.buckets.files.name}/*"]
  }
}

data "aws_iam_policy_document" "public_files" {
  statement {
    sid = "VisualEditor0"
    actions = [
      "s3:PutObject",
      "s3:GetObjectAttributes",
      "s3:GetObject",
      "s3:GetObjectVersion",
      "s3:GetObjectVersionAttributes",
      "s3:DeleteObject",
      "s3:DeleteObjectVersion",
    ]
    resources = ["arn:aws:s3:::${var.buckets.public_files.name}/*"]
  }
}

resource "aws_iam_policy" "files" {
  name        = var.buckets.files.name
  description = var.buckets.files.description
  policy      = data.aws_iam_policy_document.files.json
}

resource "aws_iam_policy" "public_files" {
  name        = var.buckets.public_files.name
  description = var.buckets.public_files.description
  policy      = data.aws_iam_policy_document.public_files.json
}

resource "aws_iam_user_policy_attachment" "files" {
  user       = var.username
  policy_arn = aws_iam_policy.files.arn
}

resource "aws_iam_user_policy_attachment" "public_files" {
  user       = var.username
  policy_arn = aws_iam_policy.public_files.arn
}
