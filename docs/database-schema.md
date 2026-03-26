# Database Schema

## Table of Contents

- [Identity_Profile](#identity_profile)
- [Blast_Radius_Score](#blast_radius_score)
- [Incident](#incident)
- [Event_Summary](#event_summary)
- [Trust_Relationship](#trust_relationship)
- [Remediation_Config](#remediation_config)
- [Remediation_Audit_Log](#remediation_audit_log)

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

---

## Remediation_Config

Stores the singleton global remediation configuration. There is exactly one record in this table (`config_id=global`).

**Primary key:** `config_id` (partition key)

| Field | Type | Description |
|---|---|---|
| config_id | String | Always `"global"` (PK) |
| risk_mode | String | Active risk mode: `monitor`, `alert`, or `enforce` |
| rules | List | Ordered list of remediation rule objects |
| excluded_arns | List | IAM ARNs exempt from all remediation |
| protected_account_ids | List | AWS account IDs exempt from all remediation |
| allowed_ip_ranges | List | CIDR ranges used by `restrict_network_access` action |

**Rule object fields:**

| Field | Type | Description |
|---|---|---|
| rule_id | String (UUID v4) | Unique rule identifier |
| name | String | Human-readable description |
| active | Boolean | Whether the rule participates in matching |
| priority | Integer | Lower = higher priority; rules evaluated in ascending order |
| min_severity | String | Minimum incident severity to match |
| detection_types | List\<String\> | Detection types that trigger this rule; empty = all |
| identity_types | List\<String\> | Identity types this rule applies to; empty = all |
| actions | List\<String\> | Ordered list of action names to execute |

**GSIs:** None (single-record table; all access is by primary key)

**TTL:** Not enabled

**Example record:**
```json
{
  "config_id": "global",
  "risk_mode": "monitor",
  "rules": [
    {
      "rule_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Disable compromised IAM users on Critical incidents",
      "active": true,
      "priority": 1,
      "min_severity": "Critical",
      "detection_types": [],
      "identity_types": ["IAMUser"],
      "actions": ["disable_iam_user", "notify_security_team"]
    }
  ],
  "excluded_arns": ["arn:aws:iam::123456789012:user/break-glass-admin"],
  "protected_account_ids": ["123456789012"],
  "allowed_ip_ranges": ["10.0.0.0/8", "192.168.1.0/24"]
}
```

---

## Remediation_Audit_Log

Append-only audit log. Every action evaluation — executed, skipped, suppressed, or failed — writes one record. A summary record (`action_name=remediation_complete`) is written after all actions complete for an incident.

**Primary key:** `audit_id` (partition key)

| Field | Type | Description |
|---|---|---|
| audit_id | String (UUID v4) | Primary key |
| incident_id | String (UUID v4) | Source incident |
| identity_arn | String | IAM identity that was evaluated |
| rule_id | String | Rule that triggered this action; empty for suppressed/no-match/summary records |
| action_name | String | Action evaluated, or `remediation_suppressed` / `no_rules_matched` / `remediation_complete` |
| outcome | String | `executed`, `skipped`, `failed`, `suppressed`, or `summary` |
| risk_mode | String | Active mode at evaluation time |
| dry_run | Boolean | Whether dry_run was active |
| timestamp | String (ISO 8601 UTC) | Evaluation time |
| details | String (JSON) | Action-specific metadata (key IDs, policy ARNs, counts) |
| reason | String | Suppression or failure reason; empty for executed outcomes |
| ttl | Number (Unix timestamp) | Auto-expiry 365 days from write time |

**GSIs:**

| Index | PK | SK | Projection | Use case |
|---|---|---|---|---|
| IdentityTimeIndex | identity_arn | timestamp | ALL | List audit entries for an identity, sorted by time |
| IncidentIndex | incident_id | timestamp | ALL | List all audit entries for a specific incident |

**TTL:** Enabled on `ttl` field (365-day expiry)

**Example record:**
```json
{
  "audit_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
  "incident_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
  "identity_arn": "arn:aws:iam::123456789012:user/attacker",
  "rule_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "action_name": "disable_iam_user",
  "outcome": "executed",
  "risk_mode": "enforce",
  "dry_run": false,
  "timestamp": "2024-01-15T10:30:00.123456+00:00",
  "details": "{\"deactivated_key_ids\": [\"AKIAIOSFODNN7EXAMPLE\"], \"login_profile_deleted\": true}",
  "reason": "",
  "ttl": 1768472400
}
```
