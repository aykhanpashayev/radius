# Table names — used as Lambda environment variables
output "table_names" {
  description = "Map of logical table name to actual DynamoDB table name"
  value = {
    identity_profile      = aws_dynamodb_table.identity_profile.name
    blast_radius_score    = aws_dynamodb_table.blast_radius_score.name
    incident              = aws_dynamodb_table.incident.name
    event_summary         = aws_dynamodb_table.event_summary.name
    trust_relationship    = aws_dynamodb_table.trust_relationship.name
    remediation_config    = aws_dynamodb_table.remediation_config.name
    remediation_audit_log = aws_dynamodb_table.remediation_audit_log.name
  }
}

# Table ARNs — used in IAM policies
output "table_arns" {
  description = "Map of logical table name to DynamoDB table ARN"
  value = {
    identity_profile      = aws_dynamodb_table.identity_profile.arn
    blast_radius_score    = aws_dynamodb_table.blast_radius_score.arn
    incident              = aws_dynamodb_table.incident.arn
    event_summary         = aws_dynamodb_table.event_summary.arn
    trust_relationship    = aws_dynamodb_table.trust_relationship.arn
    remediation_config    = aws_dynamodb_table.remediation_config.arn
    remediation_audit_log = aws_dynamodb_table.remediation_audit_log.arn
  }
}

# GSI ARNs — used in IAM policies for fine-grained access
output "gsi_arns" {
  description = "Map of table name to list of GSI ARNs"
  value = {
    identity_profile = [
      "${aws_dynamodb_table.identity_profile.arn}/index/IdentityTypeIndex",
      "${aws_dynamodb_table.identity_profile.arn}/index/AccountIndex",
    ]
    blast_radius_score = [
      "${aws_dynamodb_table.blast_radius_score.arn}/index/ScoreRangeIndex",
      "${aws_dynamodb_table.blast_radius_score.arn}/index/SeverityIndex",
    ]
    incident = [
      "${aws_dynamodb_table.incident.arn}/index/StatusIndex",
      "${aws_dynamodb_table.incident.arn}/index/SeverityIndex",
      "${aws_dynamodb_table.incident.arn}/index/IdentityIndex",
    ]
    event_summary = [
      "${aws_dynamodb_table.event_summary.arn}/index/EventIdIndex",
      "${aws_dynamodb_table.event_summary.arn}/index/EventTypeIndex",
      "${aws_dynamodb_table.event_summary.arn}/index/TimeRangeIndex",
    ]
    trust_relationship = [
      "${aws_dynamodb_table.trust_relationship.arn}/index/RelationshipTypeIndex",
      "${aws_dynamodb_table.trust_relationship.arn}/index/TargetAccountIndex",
    ]
    remediation_audit_log = [
      "${aws_dynamodb_table.remediation_audit_log.arn}/index/IdentityTimeIndex",
      "${aws_dynamodb_table.remediation_audit_log.arn}/index/IncidentIndex",
    ]
  }
}

# GSI names — used for query optimization in Lambda code
output "gsi_names" {
  description = "Map of table name to GSI names"
  value = {
    identity_profile = {
      identity_type_index = "IdentityTypeIndex"
      account_index       = "AccountIndex"
    }
    blast_radius_score = {
      score_range_index = "ScoreRangeIndex"
      severity_index    = "SeverityIndex"
    }
    incident = {
      status_index   = "StatusIndex"
      severity_index = "SeverityIndex"
      identity_index = "IdentityIndex"
    }
    event_summary = {
      event_id_index   = "EventIdIndex"
      event_type_index = "EventTypeIndex"
      time_range_index = "TimeRangeIndex"
    }
    trust_relationship = {
      relationship_type_index = "RelationshipTypeIndex"
      target_account_index    = "TargetAccountIndex"
    }
    remediation_audit_log = {
      identity_time_index = "IdentityTimeIndex"
      incident_index      = "IncidentIndex"
    }
  }
}
