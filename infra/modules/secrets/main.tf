# Secrets Manager module for Radius.
# Provisions placeholder secrets for external alert webhook integrations
# (PagerDuty, OpsGenie). Secret values are populated out-of-band — they
# are never stored in Terraform state or the git repository.
#
# To populate after provisioning:
#   aws secretsmanager put-secret-value \
#     --secret-id /radius/prod/pagerduty/integration_key \
#     --secret-string '{"integration_key":"your-key-here"}'

locals {
  common_tags = merge(
    {
      Module      = "secrets"
      Environment = var.environment
    },
    var.tags
  )

  kms_key_id = var.kms_key_arn != "" ? var.kms_key_arn : null
}

# ---------------------------------------------------------------------------
# PagerDuty integration key
# Used by Incident_Processor and Remediation_Engine to page on-call.
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "pagerduty" {
  name        = "/radius/${var.environment}/pagerduty/integration_key"
  description = "PagerDuty Events API v2 integration key for Radius ${var.environment} alerts"
  kms_key_id  = local.kms_key_id

  # Prevent accidental deletion — requires a recovery window
  recovery_window_in_days = var.environment == "prod" ? 30 : 7

  tags = merge(local.common_tags, { Service = "pagerduty" })
}

# ---------------------------------------------------------------------------
# OpsGenie API key (alternative to PagerDuty)
# ---------------------------------------------------------------------------
resource "aws_secretsmanager_secret" "opsgenie" {
  name        = "/radius/${var.environment}/opsgenie/api_key"
  description = "OpsGenie API key for Radius ${var.environment} alerts"
  kms_key_id  = local.kms_key_id

  recovery_window_in_days = var.environment == "prod" ? 30 : 7

  tags = merge(local.common_tags, { Service = "opsgenie" })
}
