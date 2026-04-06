# CloudTrail module for Radius
# Org-wide trail (prod) or single-account trail (dev).
# EventBridge integration enabled for real-time event routing.

locals {
  common_tags = merge(
    {
      Module      = "cloudtrail"
      Environment = var.environment
    },
    var.tags
  )
}

resource "aws_cloudtrail" "radius" {
  name                          = "${var.prefix}-trail"
  s3_bucket_name                = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail         = true
  is_organization_trail         = var.organization_enabled
  enable_log_file_validation    = true
  kms_key_id                    = var.kms_key_arn

  # Send events to EventBridge for real-time processing
  cloud_watch_logs_group_arn = null # Using EventBridge, not CWL delivery

  event_selector {
    read_write_type           = "WriteOnly"
    include_management_events = true
  }

  tags = local.common_tags

  depends_on = [aws_s3_bucket_policy.cloudtrail_logs]
}
