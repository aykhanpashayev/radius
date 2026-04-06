# S3 bucket for CloudTrail log storage.
# Encryption, versioning, public access block, and lifecycle policies.

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Fetch org ID when org trail is enabled — requires organizations:DescribeOrganization
data "aws_organizations_organization" "current" {
  count = var.organization_enabled ? 1 : 0
}

resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket        = "${var.prefix}-cloudtrail-logs-${data.aws_caller_identity.current.account_id}"
  force_destroy = var.environment == "dev" ? true : false

  tags = merge(local.common_tags, { Purpose = "cloudtrail-logs" })
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket                  = aws_s3_bucket.cloudtrail_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  rule {
    id     = "archive-and-expire"
    status = "Enabled"

    filter {}

    transition {
      days          = var.log_retention_days
      storage_class = "GLACIER"
    }

    expiration {
      days = var.log_expiration_days
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# Bucket policy allowing CloudTrail to write logs.
# For org-wide trails, member accounts write to AWSLogs/<org-id>/<account-id>/...
# so an additional statement covering the org prefix is required.
resource "aws_s3_bucket_policy" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid       = "AWSCloudTrailAclCheck"
          Effect    = "Allow"
          Principal = { Service = "cloudtrail.amazonaws.com" }
          Action    = "s3:GetBucketAcl"
          Resource  = aws_s3_bucket.cloudtrail_logs.arn
        },
        {
          Sid       = "AWSCloudTrailWrite"
          Effect    = "Allow"
          Principal = { Service = "cloudtrail.amazonaws.com" }
          Action    = "s3:PutObject"
          Resource  = "${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
          Condition = {
            StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
          }
        }
      ],
      # When organization_enabled = true, member accounts write under the org prefix
      var.organization_enabled ? [
        {
          Sid       = "AWSCloudTrailOrgWrite"
          Effect    = "Allow"
          Principal = { Service = "cloudtrail.amazonaws.com" }
          Action    = "s3:PutObject"
          Resource  = "${aws_s3_bucket.cloudtrail_logs.arn}/AWSLogs/${data.aws_organizations_organization.current[0].id}/*"
          Condition = {
            StringEquals = { "s3:x-amz-acl" = "bucket-owner-full-control" }
          }
        }
      ] : []
    )
  })

  depends_on = [aws_s3_bucket_public_access_block.cloudtrail_logs]
}
