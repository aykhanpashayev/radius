# SNS module for Radius incident alerting.
# Alert_Topic with KMS encryption and severity-based subscription filters.

locals {
  common_tags = merge(
    {
      Module      = "sns"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# Alert_Topic
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "alert_topic" {
  name              = "${var.prefix}-alert-topic"
  kms_master_key_id = var.kms_key_arn

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Remediation_Topic
# Receives structured remediation notifications from Remediation_Engine.
# No subscriptions managed here — consumers subscribe independently.
# ---------------------------------------------------------------------------
resource "aws_sns_topic" "remediation_topic" {
  name              = "${var.prefix}-remediation-topic"
  kms_master_key_id = var.kms_key_arn

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Email subscriptions (one per address)
# ---------------------------------------------------------------------------
resource "aws_sns_topic_subscription" "email" {
  for_each = toset(var.email_subscriptions)

  topic_arn = aws_sns_topic.alert_topic.arn
  protocol  = "email"
  endpoint  = each.value

  # Filter: only High, Very High, Critical severity
  filter_policy = jsonencode({
    severity = ["High", "Very High", "Critical"]
  })
}

# ---------------------------------------------------------------------------
# HTTPS webhook subscriptions
# ---------------------------------------------------------------------------
resource "aws_sns_topic_subscription" "https" {
  for_each = toset(var.https_subscriptions)

  topic_arn = aws_sns_topic.alert_topic.arn
  protocol  = "https"
  endpoint  = each.value

  filter_policy = jsonencode({
    severity = ["High", "Very High", "Critical"]
  })
}
