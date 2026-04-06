# AWS Organizations bootstrap module for Radius.
# Deploy this ONCE from the Organizations management account credentials,
# in a separate workspace (infra/envs/org/), before the prod application deploy.
#
# What this provisions:
#   1. Service Control Policies (SCPs) — prevent member accounts from
#      disabling CloudTrail or leaving the organization
#   2. GuardDuty delegated admin — designates the Radius security account
#      as the GuardDuty administrator for the organization
#   3. GuardDuty org configuration — auto-enables GuardDuty in new accounts

data "aws_organizations_organization" "current" {}

locals {
  common_tags = merge(
    { Module = "organizations" },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# SCP 1 — Deny disabling or tampering with CloudTrail
# Applies to all principals in the organization except the management account.
# ---------------------------------------------------------------------------
resource "aws_organizations_policy" "deny_disable_cloudtrail" {
  name        = "radius-deny-disable-cloudtrail"
  description = "Prevents any principal from stopping, deleting, or modifying the Radius organization CloudTrail. Managed by Terraform."
  type        = "SERVICE_CONTROL_POLICY"

  content = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "DenyDisableCloudTrail"
        Effect = "Deny"
        Action = [
          "cloudtrail:StopLogging",
          "cloudtrail:DeleteTrail",
          "cloudtrail:UpdateTrail",
          "cloudtrail:PutEventSelectors",
          "cloudtrail:RemoveTags",
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_organizations_policy_attachment" "deny_disable_cloudtrail" {
  policy_id = aws_organizations_policy.deny_disable_cloudtrail.id
  target_id = data.aws_organizations_organization.current.roots[0].id
}

# ---------------------------------------------------------------------------
# SCP 2 — Deny leaving the organization
# Prevents member accounts from removing themselves from monitoring scope.
# ---------------------------------------------------------------------------
resource "aws_organizations_policy" "deny_leave_organization" {
  name        = "radius-deny-leave-organization"
  description = "Prevents member accounts from leaving the AWS Organization, which would remove them from Radius monitoring scope. Managed by Terraform."
  type        = "SERVICE_CONTROL_POLICY"

  content = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "DenyLeaveOrganization"
        Effect   = "Deny"
        Action   = ["organizations:LeaveOrganization"]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_organizations_policy_attachment" "deny_leave_organization" {
  policy_id = aws_organizations_policy.deny_leave_organization.id
  target_id = data.aws_organizations_organization.current.roots[0].id
}

# ---------------------------------------------------------------------------
# GuardDuty — enable the service and designate Radius account as admin
# ---------------------------------------------------------------------------
resource "aws_guardduty_detector" "management" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
  }

  tags = local.common_tags
}

resource "aws_guardduty_organization_admin_account" "radius" {
  admin_account_id = var.security_account_id

  depends_on = [aws_guardduty_detector.management]
}

# ---------------------------------------------------------------------------
# GuardDuty org configuration — auto-enable for new member accounts
# Applied in the security account after delegation (requires a second provider
# alias pointing to the security account — see usage in envs/org/main.tf)
# ---------------------------------------------------------------------------
resource "aws_guardduty_organization_configuration" "radius" {
  auto_enable_organization_members = "NEW"
  detector_id                      = aws_guardduty_detector.management.id
}
