# DynamoDB tables for Radius
# All tables use on-demand billing and KMS encryption at rest.
# PITR is enabled for Identity_Profile, Blast_Radius_Score, and Incident (critical data).
# TTL is enabled for Event_Summary and Incident (high-volume / archival).

locals {
  common_tags = merge(
    {
      Module      = "dynamodb"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# Identity_Profile
# Stores IAM identity metadata and activity history.
# PK: identity_arn
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "identity_profile" {
  name         = "${var.prefix}-identity-profile"
  billing_mode = var.billing_mode
  hash_key     = "identity_arn"

  attribute {
    name = "identity_arn"
    type = "S"
  }

  attribute {
    name = "identity_type"
    type = "S"
  }

  attribute {
    name = "account_id"
    type = "S"
  }

  attribute {
    name = "last_activity_timestamp"
    type = "S"
  }

  # GSI: query all identities of a specific type within an account
  global_secondary_index {
    name            = "IdentityTypeIndex"
    hash_key        = "identity_type"
    range_key       = "account_id"
    projection_type = "ALL"
  }

  # GSI: query all identities in an account sorted by recent activity
  global_secondary_index {
    name            = "AccountIndex"
    hash_key        = "account_id"
    range_key       = "last_activity_timestamp"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = var.enable_pitr
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "identity-profile" })
}

# ---------------------------------------------------------------------------
# Blast_Radius_Score
# Stores current blast radius score snapshot per identity.
# PK: identity_arn
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "blast_radius_score" {
  name         = "${var.prefix}-blast-radius-score"
  billing_mode = var.billing_mode
  hash_key     = "identity_arn"

  attribute {
    name = "identity_arn"
    type = "S"
  }

  attribute {
    name = "severity_level"
    type = "S"
  }

  attribute {
    name = "score_value"
    type = "N"
  }

  attribute {
    name = "calculation_timestamp"
    type = "S"
  }

  # GSI: query identities by severity level sorted by score value
  global_secondary_index {
    name            = "ScoreRangeIndex"
    hash_key        = "severity_level"
    range_key       = "score_value"
    projection_type = "ALL"
  }

  # GSI: count identities by severity level over time (keys only for cost)
  global_secondary_index {
    name            = "SeverityIndex"
    hash_key        = "severity_level"
    range_key       = "calculation_timestamp"
    projection_type = "KEYS_ONLY"
  }

  point_in_time_recovery {
    enabled = var.enable_pitr
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "blast-radius-score" })
}

# ---------------------------------------------------------------------------
# Incident
# Tracks security incidents requiring investigation.
# PK: incident_id
# TTL: resolved incidents archived after var.incident_ttl_days
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "incident" {
  name         = "${var.prefix}-incident"
  billing_mode = var.billing_mode
  hash_key     = "incident_id"

  attribute {
    name = "incident_id"
    type = "S"
  }

  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "severity"
    type = "S"
  }

  attribute {
    name = "identity_arn"
    type = "S"
  }

  attribute {
    name = "creation_timestamp"
    type = "S"
  }

  # GSI: query incidents by status sorted by creation time
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "creation_timestamp"
    projection_type = "ALL"
  }

  # GSI: query incidents by severity sorted by creation time
  global_secondary_index {
    name            = "SeverityIndex"
    hash_key        = "severity"
    range_key       = "creation_timestamp"
    projection_type = "ALL"
  }

  # GSI: query all incidents for a specific identity (keys only for cost)
  global_secondary_index {
    name            = "IdentityIndex"
    hash_key        = "identity_arn"
    range_key       = "creation_timestamp"
    projection_type = "KEYS_ONLY"
  }

  # TTL: resolved incidents are archived after incident_ttl_days
  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.enable_pitr
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "incident" })
}

# ---------------------------------------------------------------------------
# Event_Summary
# Stores normalized CloudTrail events for analysis and audit.
# PK: identity_arn, SK: timestamp
# TTL: events expire after var.event_summary_ttl_days
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "event_summary" {
  name         = "${var.prefix}-event-summary"
  billing_mode = var.billing_mode
  hash_key     = "identity_arn"
  range_key    = "timestamp"

  attribute {
    name = "identity_arn"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "event_id"
    type = "S"
  }

  attribute {
    name = "event_type"
    type = "S"
  }

  attribute {
    name = "date_partition"
    type = "S"
  }

  # GSI: direct event lookup by CloudTrail event ID
  global_secondary_index {
    name            = "EventIdIndex"
    hash_key        = "event_id"
    projection_type = "ALL"
  }

  # GSI: query events by type sorted by time (keys only for cost)
  global_secondary_index {
    name            = "EventTypeIndex"
    hash_key        = "event_type"
    range_key       = "timestamp"
    projection_type = "KEYS_ONLY"
  }

  # GSI: efficient time-range queries across all identities
  global_secondary_index {
    name            = "TimeRangeIndex"
    hash_key        = "date_partition"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # TTL: events expire after event_summary_ttl_days
  ttl {
    attribute_name = "ttl_timestamp"
    enabled        = true
  }

  # No PITR: high-volume table with TTL enabled
  point_in_time_recovery {
    enabled = false
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "event-summary" })
}

# ---------------------------------------------------------------------------
# Remediation_Config
# Stores global remediation configuration (singleton record: config_id=global).
# PK: config_id
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "remediation_config" {
  name         = "${var.prefix}-remediation-config"
  billing_mode = var.billing_mode
  hash_key     = "config_id"

  attribute {
    name = "config_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = var.enable_pitr
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "remediation-config" })
}

# ---------------------------------------------------------------------------
# Remediation_Audit_Log
# Stores per-action audit records for all remediation executions.
# PK: audit_id
# TTL: audit entries expire after 365 days (set by Lambda)
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "remediation_audit_log" {
  name         = "${var.prefix}-remediation-audit-log"
  billing_mode = var.billing_mode
  hash_key     = "audit_id"

  attribute {
    name = "audit_id"
    type = "S"
  }

  attribute {
    name = "identity_arn"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  attribute {
    name = "incident_id"
    type = "S"
  }

  # GSI: query audit entries by identity sorted by time (for cooldown/rate-limit checks)
  global_secondary_index {
    name            = "IdentityTimeIndex"
    hash_key        = "identity_arn"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # GSI: query audit entries by incident (keys only for cost)
  global_secondary_index {
    name            = "IncidentIndex"
    hash_key        = "incident_id"
    range_key       = "timestamp"
    projection_type = "KEYS_ONLY"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = var.enable_pitr
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "remediation-audit-log" })
}

# ---------------------------------------------------------------------------
# Trust_Relationship
# Records cross-account and service-to-service trust edges.
# PK: source_arn, SK: target_arn
# ---------------------------------------------------------------------------
resource "aws_dynamodb_table" "trust_relationship" {
  name         = "${var.prefix}-trust-relationship"
  billing_mode = var.billing_mode
  hash_key     = "source_arn"
  range_key    = "target_arn"

  attribute {
    name = "source_arn"
    type = "S"
  }

  attribute {
    name = "target_arn"
    type = "S"
  }

  attribute {
    name = "relationship_type"
    type = "S"
  }

  attribute {
    name = "discovery_timestamp"
    type = "S"
  }

  attribute {
    name = "target_account_id"
    type = "S"
  }

  # GSI: query relationships by type sorted by discovery time
  global_secondary_index {
    name            = "RelationshipTypeIndex"
    hash_key        = "relationship_type"
    range_key       = "discovery_timestamp"
    projection_type = "ALL"
  }

  # GSI: query relationships targeting a specific account (keys only for cost)
  global_secondary_index {
    name            = "TargetAccountIndex"
    hash_key        = "target_account_id"
    range_key       = "discovery_timestamp"
    projection_type = "KEYS_ONLY"
  }

  # No PITR: can be rebuilt from CloudTrail events
  point_in_time_recovery {
    enabled = false
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  tags = merge(local.common_tags, { Table = "trust-relationship" })
}
