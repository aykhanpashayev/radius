# AWS Backup module for Radius DynamoDB tables.
# Provides daily point-in-time backups with configurable retention
# and optional cross-region copy for disaster recovery.
#
# This supplements (not replaces) DynamoDB PITR:
#   - PITR:       continuous, 35-day window, same-region only
#   - AWS Backup: daily snapshots, configurable retention, cross-region capable
#
# Tables backed up: the 5 PITR-enabled tables passed via var.table_arns
#   - identity_profile, blast_radius_score, incident,
#     remediation_config, remediation_audit_log

data "aws_caller_identity" "current" {}

locals {
  common_tags = merge(
    {
      Module      = "backup"
      Environment = var.environment
    },
    var.tags
  )

  cross_region_enabled = var.copy_to_region != ""
}

# ---------------------------------------------------------------------------
# IAM role for AWS Backup service
# ---------------------------------------------------------------------------
resource "aws_iam_role" "backup" {
  name = "${var.prefix}-backup-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "backup.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "backup_dynamodb" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForBackup"
}

resource "aws_iam_role_policy_attachment" "backup_restore" {
  role       = aws_iam_role.backup.name
  policy_arn = "arn:aws:iam::aws:policy/AWSBackupServiceRolePolicyForRestores"
}

# ---------------------------------------------------------------------------
# Backup vault — KMS-encrypted, primary region
# ---------------------------------------------------------------------------
resource "aws_backup_vault" "radius" {
  name        = "${var.prefix}-backup-vault"
  kms_key_arn = var.kms_key_arn
  tags        = local.common_tags
}

# ---------------------------------------------------------------------------
# Backup plan — daily backups at 02:00 UTC
# ---------------------------------------------------------------------------
resource "aws_backup_plan" "radius" {
  name = "${var.prefix}-backup-plan"

  rule {
    rule_name         = "daily-backup"
    target_vault_name = aws_backup_vault.radius.name
    schedule          = "cron(0 2 * * ? *)" # 02:00 UTC every day

    lifecycle {
      delete_after = var.backup_retention_days
    }

    # Cross-region copy — enabled only when copy_to_region is set
    dynamic "copy_action" {
      for_each = local.cross_region_enabled ? [1] : []
      content {
        destination_vault_arn = "arn:aws:backup:${var.copy_to_region}:${data.aws_caller_identity.current.account_id}:backup-vault:${var.prefix}-backup-vault-dr"
        lifecycle {
          delete_after = var.copy_retention_days
        }
      }
    }
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Backup selection — covers the PITR-enabled DynamoDB tables
# ---------------------------------------------------------------------------
resource "aws_backup_selection" "radius_tables" {
  name         = "${var.prefix}-dynamodb-tables"
  plan_id      = aws_backup_plan.radius.id
  iam_role_arn = aws_iam_role.backup.arn

  resources = var.table_arns
}
