# KMS keys for Radius
# One key per service boundary: DynamoDB, Lambda, SNS, CloudTrail.
# Separate keys allow independent key rotation and access control policies.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name

  common_tags = merge(
    {
      Module      = "kms"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# DynamoDB KMS Key
# Used to encrypt all five DynamoDB tables at rest.
# ---------------------------------------------------------------------------
resource "aws_kms_key" "dynamodb" {
  description             = "Radius ${var.environment} - DynamoDB encryption"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowDynamoDB"
        Effect = "Allow"
        Principal = {
          Service = "dynamodb.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, { Service = "dynamodb" })
}

resource "aws_kms_alias" "dynamodb" {
  name          = "alias/${var.prefix}-dynamodb"
  target_key_id = aws_kms_key.dynamodb.key_id
}

# ---------------------------------------------------------------------------
# Lambda KMS Key
# Used to encrypt Lambda environment variables.
# ---------------------------------------------------------------------------
resource "aws_kms_key" "lambda" {
  description             = "Radius ${var.environment} - Lambda encryption"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowLambda"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, { Service = "lambda" })
}

resource "aws_kms_alias" "lambda" {
  name          = "alias/${var.prefix}-lambda"
  target_key_id = aws_kms_key.lambda.key_id
}

# ---------------------------------------------------------------------------
# SNS KMS Key
# Used to encrypt SNS Alert_Topic messages at rest.
# ---------------------------------------------------------------------------
resource "aws_kms_key" "sns" {
  description             = "Radius ${var.environment} - SNS encryption"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowSNS"
        Effect = "Allow"
        Principal = {
          Service = "sns.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        # Lambda (Incident_Processor) must be able to publish encrypted messages
        Sid    = "AllowLambdaPublish"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey*",
          "kms:Decrypt"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, { Service = "sns" })
}

resource "aws_kms_alias" "sns" {
  name          = "alias/${var.prefix}-sns"
  target_key_id = aws_kms_key.sns.key_id
}

# ---------------------------------------------------------------------------
# CloudTrail KMS Key
# Used to encrypt CloudTrail log files stored in S3.
# ---------------------------------------------------------------------------
resource "aws_kms_key" "cloudtrail" {
  description             = "Radius ${var.environment} - CloudTrail encryption"
  deletion_window_in_days = var.deletion_window_in_days
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${local.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudTrailEncrypt"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey*",
          "kms:DescribeKey"
        ]
        Resource = "*"
        Condition = {
          StringLike = {
            "kms:EncryptionContext:aws:cloudtrail:arn" = "arn:aws:cloudtrail:${local.region}:${local.account_id}:trail/*"
          }
        }
      },
      {
        Sid    = "AllowCloudTrailDescribe"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "kms:DescribeKey"
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, { Service = "cloudtrail" })
}

resource "aws_kms_alias" "cloudtrail" {
  name          = "alias/${var.prefix}-cloudtrail"
  target_key_id = aws_kms_key.cloudtrail.key_id
}
