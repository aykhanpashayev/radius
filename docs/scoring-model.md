# Blast Radius Score — Scoring Model Reference

## Overview

The Blast Radius Score is a deterministic, rule-based integer in the range **0–100** that quantifies the potential damage an IAM identity could cause if compromised.

Key properties:

- **Rule-based and transparent** — each point contribution is traceable to a named rule
- **Deterministic** — the same input data always produces the same score
- **Additive with a hard cap** — rule contributions are summed and capped at 100
- **Explainable** — the `contributing_factors` field lists every rule that fired and its point value
- **Windowed** — scores are calculated over the last 90 days of CloudTrail activity (max 1,000 events)

---

## Severity Levels

| Score range | Severity level |
|-------------|----------------|
| 0 – 19      | Low            |
| 20 – 39     | Moderate       |
| 40 – 59     | High           |
| 60 – 79     | Very High      |
| 80 – 100    | Critical       |

---

## Scoring Rules

Eight rules contribute to the total score. Each rule is independent and stateless — rules read from `ScoringContext` but never write to DynamoDB.

### 1. AdminPrivileges

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `admin_privileges` |
| `rule_name`       | `AdminPrivileges` |
| `max_contribution`| 25 |

Detects IAM write operations and broad service usage.

| Condition | Points |
|-----------|--------|
| Any IAM write event present (`CreateUser`, `CreateRole`, `AttachUserPolicy`, `AttachRolePolicy`, `PutUserPolicy`, `PutRolePolicy`, `CreatePolicy`, `CreatePolicyVersion`) | +20 |
| 5 or more distinct AWS services accessed across all events | +5 |

Maximum: 25 (both conditions met).

---

### 2. IAMPermissionsScope

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `iam_permissions_scope` |
| `rule_name`       | `IAMPermissionsScope` |
| `max_contribution`| 20 |

Scores the breadth of distinct IAM actions performed.

| Distinct IAM event types | Points |
|--------------------------|--------|
| 0                        | 0      |
| 1 – 4                    | 5      |
| 5 – 9                    | 10     |
| 10+                      | 20     |

---

### 3. IAMModification

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `iam_modification` |
| `rule_name`       | `IAMModification` |
| `max_contribution`| 20 |

Counts IAM mutation events that indicate policy tampering or privilege changes.

Mutation events: `AttachUserPolicy`, `AttachRolePolicy`, `AttachGroupPolicy`, `PutUserPolicy`, `PutRolePolicy`, `PutGroupPolicy`, `CreatePolicyVersion`, `SetDefaultPolicyVersion`, `AddUserToGroup`.

| Mutation event count | Points |
|----------------------|--------|
| 0                    | 0      |
| 1 – 2                | 10     |
| 3+                   | 20     |

---

### 4. LoggingDisruption

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `logging_disruption` |
| `rule_name`       | `LoggingDisruption` |
| `max_contribution`| 20 |

Fires if any event that disrupts audit trail visibility is present.

Disruption events: `StopLogging`, `DeleteTrail`, `UpdateTrail`, `PutEventSelectors`, `DeleteFlowLogs`, `DeleteLogGroup`, `DeleteLogStream`.

| Condition | Points |
|-----------|--------|
| Any disruption event present | 20 |
| No disruption events         | 0  |

---

### 5. CrossAccountTrust

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `cross_account_trust` |
| `rule_name`       | `CrossAccountTrust` |
| `max_contribution`| 15 |

Scores based on the number of cross-account trust relationships associated with the identity.

| CrossAccount trust count | Points |
|--------------------------|--------|
| 0                        | 0      |
| 1                        | 5      |
| 2 – 3                    | 10     |
| 4+                       | 15     |

---

### 6. RoleChaining

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `role_chaining` |
| `rule_name`       | `RoleChaining` |
| `max_contribution`| 10 |

Counts AssumeRole-type events, indicating potential role chaining via STS.

AssumeRole events: `AssumeRole`, `AssumeRoleWithSAML`, `AssumeRoleWithWebIdentity`.

| AssumeRole event count | Points |
|------------------------|--------|
| 0                      | 0      |
| 1 – 2                  | 5      |
| 3+                     | 10     |

---

### 7. PrivilegeEscalation

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `privilege_escalation` |
| `rule_name`       | `PrivilegeEscalation` |
| `max_contribution`| 15 |

Counts distinct privilege escalation indicators present in the event window.

| Indicator | Condition |
|-----------|-----------|
| 1 | `CreateUser` AND `AttachUserPolicy` both present |
| 2 | `CreatePolicyVersion` present |
| 3 | `AddUserToGroup` present |
| 4 | `PassRole` present |

| Indicator count | Points |
|-----------------|--------|
| 0               | 0      |
| 1               | 8      |
| 2+              | 15     |

---

### 8. LateralMovement

| Attribute         | Value |
|-------------------|-------|
| `rule_id`         | `lateral_movement` |
| `rule_name`       | `LateralMovement` |
| `max_contribution`| 10 |

Awards points for indicators of lateral movement across accounts or services.

| Indicator | Condition | Points |
|-----------|-----------|--------|
| Cross-account AssumeRole | Any `AssumeRole` event targets a role in a different AWS account | +5 (once) |
| EC2 instance launch | Any `RunInstances` event present | +3 |
| Federation | Any `GetFederationToken` or `AssumeRoleWithWebIdentity` event present | +2 |

Maximum: 10 (all indicators present, capped).

---

## Contributing Factors Format

The `contributing_factors` field in a `ScoreResult` is a list of strings, one per rule that contributed non-zero points:

```
"<rule_name>: +<points>"
```

Example:

```json
"contributing_factors": [
  "AdminPrivileges: +20",
  "IAMPermissionsScope: +10",
  "LoggingDisruption: +20"
]
```

Rules that contribute 0 points are omitted.

---

## Worked Example

**Identity:** `arn:aws:iam::123456789012:role/ci-deploy`

**Events in last 90 days:**

| Event | Service |
|-------|---------|
| `iam:CreateRole` | iam |
| `iam:AttachRolePolicy` | iam |
| `iam:PutRolePolicy` | iam |
| `cloudtrail:StopLogging` | cloudtrail |
| `s3:PutObject` | s3 |
| `ec2:RunInstances` | ec2 |
| `sts:AssumeRole` (→ account 999999999999) | sts |

**Trust relationships:** 2 CrossAccount trusts

**Rule evaluation:**

| Rule | Reason | Points |
|------|--------|--------|
| AdminPrivileges | IAM write events present (+20); 4 distinct services, not 5+ (+0) | 20 |
| IAMPermissionsScope | 3 distinct IAM actions (1–4 range) | 5 |
| IAMModification | 2 mutation events (`AttachRolePolicy`, `PutRolePolicy`) | 10 |
| LoggingDisruption | `StopLogging` present | 20 |
| CrossAccountTrust | 2 cross-account trusts | 10 |
| RoleChaining | 1 AssumeRole event | 5 |
| PrivilegeEscalation | No indicators | 0 |
| LateralMovement | Cross-account AssumeRole (+5) + RunInstances (+3) | 8 |

**Total before cap:** 20 + 5 + 10 + 20 + 10 + 5 + 0 + 8 = **78**

**Final score:** 78 — **Very High**

**ScoreResult:**

```json
{
  "identity_arn": "arn:aws:iam::123456789012:role/ci-deploy",
  "score_value": 78,
  "severity_level": "Very High",
  "contributing_factors": [
    "AdminPrivileges: +20",
    "IAMPermissionsScope: +5",
    "IAMModification: +10",
    "LoggingDisruption: +20",
    "CrossAccountTrust: +10",
    "RoleChaining: +5",
    "LateralMovement: +8"
  ],
  "calculation_timestamp": "2026-03-16T10:00:00.000000+00:00",
  "previous_score": 45,
  "score_change": 33
}
```

---

## Invocation Modes

Score_Engine supports two invocation modes determined by the event payload.

### Single-identity mode

Triggered by Event_Normalizer after each processed CloudTrail event.

**Payload:**
```json
{ "identity_arn": "arn:aws:iam::123456789012:user/alice" }
```

Scores one identity and writes the result to `Blast_Radius_Score`.

### Batch mode

Triggered by EventBridge on a schedule. Rescores all active identities.

**Payload:** `{}` (empty object)

Scans `Identity_Profile` for all known identities and scores each one sequentially.

**Schedules:**

| Environment | Schedule |
|-------------|----------|
| dev         | Every 24 hours |
| prod        | Every 6 hours  |

---

## Data Sources

`ScoringContext.build()` fetches all data before any rule runs. Rules are read-only.

| Data | Source | Filter |
|------|--------|--------|
| Identity profile | `Identity_Profile` table | Primary key lookup |
| Events | `Event_Summary` table | Last 90 days, max 1,000 items |
| Trust relationships | `Trust_Relationship` table | `source_arn = identity_arn` |
| Open incidents | `Incident` table (IdentityIndex GSI) | `status in {open, investigating}` |
