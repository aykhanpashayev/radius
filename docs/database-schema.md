# Database Schema

All tables use on-demand billing and KMS encryption. PITR is enabled on Identity_Profile, Blast_Radius_Score, and Incident tables.

## Identity_Profile

Stores one record per IAM identity observed in CloudTrail events.

**Primary key:** `identity_arn` (partition key)

| Field | Type | Description |
|---|---|---|
| identity_arn | String | Full IAM ARN (PK) |
| identity_type | String | IAMUser, AssumedRole, or AWSService |
| account_id | String | 12-digit AWS account ID |
| last_activity_timestamp | String | ISO 8601 timestamp of most recent event |
| status | String | active or inactive |
| tags | Map | IAM tags from CloudTrail metadata |

**GSIs:**

| Index | PK | SK | Projection | Use case |
|---|---|---|---|---|
| IdentityTypeIndex | identity_type | account_id | ALL | Filter by type and account |
| AccountIndex | account_id | last_activity_timestamp | ALL | List identities by account, sorted by activity |

**PITR:** Enabled

---

## Blast_Radius_Score

Stores the current blast radius score snapshot per identity. Overwritten on each calculation.

**Primary key:** `identity_arn` (partition key)

| Field | Type | Description |
|---|---|---|
| identity_arn | String | Full IAM ARN (PK) |
| score_value | Number | 0–100 blast radius score |
| severity_level | String | Low / Moderate / High / Very High / Critical |
| calculation_timestamp | String | ISO 8601 timestamp of last calculation |
| contributing_factors | List | List of factor identifiers explaining the score |

**Severity thresholds:** 0–19 Low, 20–39 Moderate, 40–59 High, 60–79 Very High, 80–100 Critical

**GSIs:**

| Index | PK | SK | Projection | Use case |
|---|---|---|---|---|
| ScoreRangeIndex | severity_level | score_value | ALL | Filter by severity and score range |
| SeverityIndex | severity_level | calculation_timestamp | KEYS_ONLY | List identities by severity, sorted by recency |

**PITR:** Enabled

---

## Incident

Stores security incidents created by Incident_Processor.

**Primary key:** `incident_id` (partition key)

| Field | Type | Description |
|---|---|---|
| incident_id | String | UUID v4 (PK) |
| identity_arn | String | Identity involved in the incident |
| detection_type | String | Detection rule identifier |
| severity | String | Low / Moderate / High / Very High / Critical |
| confidence | Number | 0–100 confidence score |
| status | String | open / investigating / resolved / false_positive |
| creation_timestamp | String | ISO 8601 creation time |
| update_timestamp | String | ISO 8601 last update time |
| related_event_ids | List | CloudTrail event IDs that triggered this incident |
| status_history | List | List of {status, timestamp} transition records |
| notes | String | Analyst notes |
| assigned_to | String | Assigned analyst |
| ttl | Number | Unix epoch expiry (set for resolved/false_positive) |

**Valid status transitions:** open → investigating → resolved, open → false_positive

**GSIs:**

| Index | PK | SK | Projection | Use case |
|---|---|---|---|---|
| StatusIndex | status | creation_timestamp | ALL | List incidents by status |
| SeverityIndex | severity | creation_timestamp | ALL | List incidents by severity |
| IdentityIndex | identity_arn | creation_timestamp | KEYS_ONLY | List incidents for an identity |

**TTL:** Enabled on `ttl` field  
**PITR:** Enabled

---

## Event_Summary

Stores normalized CloudTrail event records. TTL expires records after 90 days.

**Primary key:** `identity_arn` (partition key) + `timestamp` (sort key)

| Field | Type | Description |
|---|---|---|
| identity_arn | String | Identity ARN (PK) |
| timestamp | String | ISO 8601 event time (SK) |
| event_id | String | CloudTrail eventID |
| event_name | String | CloudTrail eventName |
| event_type | String | Normalized event category |
| source_ip | String | Source IP address |
| user_agent | String | User agent string |
| date_partition | String | YYYY-MM-DD for TimeRangeIndex |
| event_parameters | Map | Sanitized request parameters (≤10KB) |
| ttl | Number | Unix epoch expiry (90 days) |

**GSIs:**

| Index | PK | SK | Projection | Use case |
|---|---|---|---|---|
| EventIdIndex | event_id | — | ALL | Direct lookup by CloudTrail event ID |
| EventTypeIndex | event_type | timestamp | KEYS_ONLY | Filter by event type |
| TimeRangeIndex | date_partition | timestamp | ALL | Time-range queries by day |

**TTL:** Enabled on `ttl` field (90-day expiry)

---

## Trust_Relationship

Records trust edges between IAM identities discovered from AssumeRole events.

**Primary key:** `source_arn` (partition key) + `target_arn` (sort key)

| Field | Type | Description |
|---|---|---|
| source_arn | String | Identity that assumed the role (PK) |
| target_arn | String | Role that was assumed (SK) |
| relationship_type | String | AssumeRole, InstanceProfile, etc. |
| target_account_id | String | Account ID of the target role |
| discovery_timestamp | String | ISO 8601 time of first observation |
| event_count | Number | Number of times this edge has been observed |

**GSIs:**

| Index | PK | SK | Projection | Use case |
|---|---|---|---|---|
| RelationshipTypeIndex | relationship_type | discovery_timestamp | ALL | Filter by relationship type |
| TargetAccountIndex | target_account_id | discovery_timestamp | KEYS_ONLY | Find cross-account relationships |
