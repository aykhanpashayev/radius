# API Reference

## Table of Contents

- [Identities](#identities)
- [Scores](#scores)
- [Incidents](#incidents)
- [Remediation](#remediation)
- [Events](#events)
- [Trust Relationships](#trust-relationships)
- [Error Responses](#error-responses)

Base URL: `https://{api-id}.execute-api.{region}.amazonaws.com/{env}`

All responses use the envelope format:
```json
{
  "data": [...],
  "metadata": { "count": 25, "next_token": "...", "query_time_ms": 12.4 }
}
```
Single-item responses return the item directly (no envelope).

Pagination: pass `next_token` from the previous response as a query parameter to fetch the next page. Default page size is 25, maximum is 100.

---

## Identities

### GET /identities

List identity profiles.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| identity_type | string | Filter by IAMUser, AssumedRole, or AWSService |
| account_id | string | Filter by 12-digit AWS account ID |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor from previous response |

**Response:** 200 with identity profile array.

---

### GET /identities/{arn}

Retrieve a single identity profile. URL-encode the ARN.

**Response:** 200 with identity profile object, or 404 if not found.

---

## Scores

### GET /scores

List blast radius scores.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| severity_level | string | Filter by Low / Moderate / High / Very High / Critical |
| min_score | number | Minimum score value (0–100) |
| max_score | number | Maximum score value (0–100) |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Note:** `severity_level` and `min_score`/`max_score` cannot be combined in a single query.

**Response:** 200 with score array.

---

### GET /scores/{arn}

Retrieve the blast radius score for a specific identity. URL-encode the ARN.

**Response:** 200 with score object, or 404 if not found.

---

## Incidents

### GET /incidents

List incidents.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| status | string | Filter by open / investigating / resolved / false_positive |
| severity | string | Filter by severity level |
| identity_arn | string | Filter by identity ARN |
| start_date | string | ISO 8601 start of creation_timestamp range |
| end_date | string | ISO 8601 end of creation_timestamp range |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Unsupported combinations:** `identity_arn` + `status` together returns 400. Use one filter at a time.

**Response:** 200 with incident array.

---

### GET /incidents/{id}

Retrieve a single incident by ID.

**Response:** 200 with incident object, or 404 if not found.

---

### PATCH /incidents/{id}

Update incident status.

**Request body:**
```json
{ "status": "investigating" }
```

**Valid transitions:**
- open → investigating
- open → false_positive
- investigating → resolved
- investigating → false_positive

**Response:** 200 with updated incident object, 400 for invalid transition, 404 if not found.

---

## Remediation

### GET /remediation/config

Return the global remediation configuration (risk mode, rules, exclusions).

**Response:** 200 with config object.

```json
{
  "config_id": "global",
  "risk_mode": "monitor",
  "rules": [
    {
      "rule_id": "a1b2c3d4-...",
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
  "allowed_ip_ranges": ["10.0.0.0/8"]
}
```

---

### PUT /remediation/config/mode

Update the global risk mode.

**Request body:**
```json
{ "risk_mode": "enforce" }
```

**Valid values:** `monitor`, `alert`, `enforce`.

**Response:** 200 on success, 400 for invalid mode.

```json
{ "risk_mode": "enforce", "updated": true }
```

---

### GET /remediation/rules

Return the rules list from the global config.

**Response:** 200 with rules array (same structure as the `rules` field in `GET /remediation/config`).

---

### POST /remediation/rules

Append a new rule to the global config.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| name | string | yes | Human-readable rule description |
| min_severity | string | no | Minimum severity to match (default: `Low`) |
| actions | array | yes | Ordered list of action names to execute |
| priority | integer | no | Lower = higher priority (default: 100) |
| detection_types | array | no | Detection types to match; empty = all |
| identity_types | array | no | Identity types to match; empty = all |
| active | boolean | no | Whether rule participates in matching (default: `true`) |

**Valid action names:** `disable_iam_user`, `remove_risky_policies`, `block_role_assumption`, `restrict_network_access`, `notify_security_team`

**Valid min_severity values:** `Low`, `Moderate`, `High`, `Very High`, `Critical`

**Example request:**
```json
{
  "name": "Disable compromised IAM users on Critical incidents",
  "priority": 1,
  "min_severity": "Critical",
  "detection_types": [],
  "identity_types": ["IAMUser"],
  "actions": ["disable_iam_user", "notify_security_team"]
}
```

**Response:** 200 with the created rule object (includes generated `rule_id`), 400 for validation errors.

---

### DELETE /remediation/rules/{rule_id}

Remove a rule from the global config by its UUID.

**Response:** 200 on success, 404 if rule not found.

```json
{ "rule_id": "a1b2c3d4-...", "deleted": true }
```

---

### GET /remediation/audit

List remediation audit log entries.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| incident_id | string | Filter by incident UUID (uses IncidentIndex GSI) |
| identity_arn | string | Filter by identity ARN (uses IdentityTimeIndex GSI) |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor from previous response |

**Unsupported combinations:** `incident_id` + `identity_arn` together returns 400.

**Response:** 200 with audit entry array.

```json
[
  {
    "audit_id": "uuid-v4",
    "incident_id": "uuid-v4",
    "identity_arn": "arn:aws:iam::123456789012:user/attacker",
    "rule_id": "uuid-v4",
    "action_name": "disable_iam_user",
    "outcome": "executed",
    "risk_mode": "enforce",
    "dry_run": false,
    "timestamp": "2024-01-15T10:30:00Z",
    "details": "{\"deactivated_key_ids\": [\"AKIAIOSFODNN7EXAMPLE\"]}",
    "reason": "",
    "ttl": 1736936400
  }
]
```

**Outcome values:** `executed`, `skipped`, `failed`, `suppressed`, `summary`

---

## Events

### GET /events

List event summaries.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| identity_arn | string | Filter by identity ARN (queries primary table) |
| event_type | string | Filter by event type (queries EventTypeIndex) |
| start_date | string | ISO 8601 start date (queries TimeRangeIndex) |
| end_date | string | ISO 8601 end date |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Unsupported combinations:** `identity_arn` + `event_type` together returns 400.

**Response:** 200 with event summary array.

---

### GET /events/{id}

Retrieve a single event summary by CloudTrail event ID.

**Response:** 200 with event summary object, or 404 if not found.

---

## Trust Relationships

### GET /trust-relationships

List trust relationships.

**Query parameters:**

| Parameter | Type | Description |
|---|---|---|
| source_arn | string | Filter by source identity ARN |
| target_account_id | string | Filter by target account ID |
| relationship_type | string | Filter by relationship type |
| limit | integer | Page size (1–100, default 25) |
| next_token | string | Pagination cursor |

**Unsupported combinations:** `source_arn` + `relationship_type` together returns 400.

**Response:** 200 with trust relationship array.

---

## Error Responses

| Status | Meaning |
|---|---|
| 400 | Bad request — invalid parameters or unsupported query combination |
| 404 | Resource not found |
| 500 | Internal server error — check CloudWatch logs |

Error response format:
```json
{ "error": "Bad Request", "message": "Filtering by both 'identity_arn' and 'status' is not supported." }
```
