# GSI Reference Documentation
#
# This file documents the Global Secondary Index access patterns for all
# Radius DynamoDB tables. GSI definitions live in main.tf alongside their
# parent table resources. This file serves as a quick reference for
# engineers writing DynamoDB queries in Lambda functions.
#
# ---------------------------------------------------------------------------
# Identity_Profile GSIs
# ---------------------------------------------------------------------------
#
# IdentityTypeIndex
#   PK: identity_type (S)   SK: account_id (S)   Projection: ALL
#   Use: GET /identities?identity_type=IAMUser&account_id=123456789012
#   Query: identity_type = :type AND account_id = :account
#
# AccountIndex
#   PK: account_id (S)   SK: last_activity_timestamp (S)   Projection: ALL
#   Use: GET /identities?account_id=123456789012 (sorted by recent activity)
#   Query: account_id = :account, sort by last_activity_timestamp DESC
#
# ---------------------------------------------------------------------------
# Blast_Radius_Score GSIs
# ---------------------------------------------------------------------------
#
# ScoreRangeIndex
#   PK: severity_level (S)   SK: score_value (N)   Projection: ALL
#   Use: GET /scores?severity_level=Critical (sorted by score)
#   Query: severity_level = :severity AND score_value BETWEEN :min AND :max
#
# SeverityIndex
#   PK: severity_level (S)   SK: calculation_timestamp (S)   Projection: KEYS_ONLY
#   Use: Count identities by severity level over time
#   Query: severity_level = :severity AND calculation_timestamp >= :since
#
# ---------------------------------------------------------------------------
# Incident GSIs
# ---------------------------------------------------------------------------
#
# StatusIndex
#   PK: status (S)   SK: creation_timestamp (S)   Projection: ALL
#   Use: GET /incidents?status=open (sorted by newest first)
#   Query: status = :status AND creation_timestamp BETWEEN :start AND :end
#
# SeverityIndex
#   PK: severity (S)   SK: creation_timestamp (S)   Projection: ALL
#   Use: GET /incidents?severity=Critical (sorted by newest first)
#   Query: severity = :severity AND creation_timestamp BETWEEN :start AND :end
#
# IdentityIndex
#   PK: identity_arn (S)   SK: creation_timestamp (S)   Projection: KEYS_ONLY
#   Use: Count incidents for a specific identity
#   Query: identity_arn = :arn
#   Note: Returns keys only — fetch full items via primary key if needed
#
# UNSUPPORTED COMBINATIONS (return HTTP 400):
#   - identity_arn + status (no composite GSI exists)
#   - identity_arn + severity (no composite GSI exists)
#   - identity_arn + date range (use primary table scan with filter — not supported in Phase 2)
#
# ---------------------------------------------------------------------------
# Event_Summary GSIs
# ---------------------------------------------------------------------------
#
# EventIdIndex
#   PK: event_id (S)   Projection: ALL
#   Use: GET /events/{id} — direct lookup by CloudTrail event ID
#   Query: event_id = :event_id
#
# EventTypeIndex
#   PK: event_type (S)   SK: timestamp (S)   Projection: KEYS_ONLY
#   Use: GET /events?event_type=AssumeRole (sorted by time)
#   Query: event_type = :type AND timestamp BETWEEN :start AND :end
#   Note: Returns keys only — fetch full items via primary key if needed
#
# TimeRangeIndex
#   PK: date_partition (S)   SK: timestamp (S)   Projection: ALL
#   Use: GET /events?start_date=2024-01-15&end_date=2024-01-16
#   Query: date_partition = :date AND timestamp BETWEEN :start AND :end
#
# UNSUPPORTED COMBINATIONS (return HTTP 400):
#   - identity_arn + event_type (no composite GSI exists)
#   - identity_arn + date range (use primary key query instead)
#
# ---------------------------------------------------------------------------
# Trust_Relationship GSIs
# ---------------------------------------------------------------------------
#
# RelationshipTypeIndex
#   PK: relationship_type (S)   SK: discovery_timestamp (S)   Projection: ALL
#   Use: GET /trust-relationships?relationship_type=CrossAccount
#   Query: relationship_type = :type AND discovery_timestamp >= :since
#
# TargetAccountIndex
#   PK: target_account_id (S)   SK: discovery_timestamp (S)   Projection: KEYS_ONLY
#   Use: GET /trust-relationships?target_account_id=123456789012
#   Query: target_account_id = :account
#   Note: Returns keys only — fetch full items via primary key if needed
#
# UNSUPPORTED COMBINATIONS (return HTTP 400):
#   - source_arn + relationship_type (no composite GSI exists)
#   - source_arn + target_account_id (no composite GSI exists)
