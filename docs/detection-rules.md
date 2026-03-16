# Detection Rules Reference

Phase 4 of Radius replaces the Detection_Engine placeholder with a real, rule-based detection engine. This document describes all 7 detection rules, the two rule types, the detection pipeline, and deduplication behavior.

---

## Detection Pipeline

```
Event_Normalizer
    └── invokes Detection_Engine (async)
            │
            ▼
    DetectionContext.build()
    (2 DynamoDB queries: 60m events + 30d prior services)
            │
            ▼
    RuleEngine.evaluate(event_summary, context)
    (evaluates all 7 rules)
            │
            ├── Finding → Incident_Processor (async invoke)
            ├── Finding → Incident_Processor (async invoke)
            └── ...
                    │
                    ▼
            Incident table (DynamoDB)
```

Each normalized CloudTrail event flows from Event_Normalizer into Detection_Engine. The engine builds a `DetectionContext` (two DynamoDB queries), evaluates all rules, and forwards each triggered `Finding` to Incident_Processor via async Lambda invocation.

---

## Rule Types

### Single-Event Rules

Operate on the Event_Summary dict only. No DynamoDB reads inside the rule. Fully deterministic given the event alone.

Rules: CrossAccountRoleAssumption, LoggingDisruption, RootUserActivity

### Context-Aware Rules

Receive a pre-fetched `DetectionContext` alongside the event. The context contains:
- `recent_events_60m` — events in the last 60 minutes for this identity
- `recent_events_5m` — derived in-memory from `recent_events_60m` (no extra query)
- `prior_services_30d` — distinct services used in events strictly before the current event timestamp

Rules: PrivilegeEscalation, IAMPolicyModificationSpike, APIBurstAnomaly, UnusualServiceUsage

---

## Severity Levels

| Severity   | Meaning                                      |
|------------|----------------------------------------------|
| Low        | Informational — worth tracking               |
| Moderate   | Suspicious — warrants investigation          |
| High       | Likely malicious — prompt response needed    |
| Very High  | Serious threat — immediate action required   |
| Critical   | Active attack or cover-up — escalate now     |

---

## Confidence Values

Confidence is a static integer (0–100) defined per rule in Phase 4. It represents the rule author's certainty that a trigger indicates genuine malicious activity. Dynamic confidence tuning based on historical false-positive rates is deferred to a future phase.

---

## Rules

### 1. PrivilegeEscalation

| Attribute     | Value                    |
|---------------|--------------------------|
| `rule_id`     | `privilege_escalation`   |
| `rule_name`   | `PrivilegeEscalation`    |
| `severity`    | High                     |
| `confidence`  | 80                       |
| Type          | Context-aware            |

Detects privilege escalation via direct IAM actions or a combined create-then-attach pattern.

Trigger conditions:
- Any of `CreatePolicyVersion`, `AddUserToGroup`, `PassRole` (single-event)
- `AttachUserPolicy` when `CreateUser` appears in `recent_events_60m` (combined indicator)

Example triggering event:
```json
{
  "event_type": "iam:PassRole",
  "identity_arn": "arn:aws:iam::123456789012:user/alice"
}
```

---

### 2. IAMPolicyModificationSpike

| Attribute     | Value                            |
|---------------|----------------------------------|
| `rule_id`     | `iam_policy_modification_spike`  |
| `rule_name`   | `IAMPolicyModificationSpike`     |
| `severity`    | High                             |
| `confidence`  | 75                               |
| Type          | Context-aware                    |

Detects a burst of IAM policy mutations within a 60-minute window.

Trigger condition: 5 or more of the following events in `recent_events_60m`:
`AttachUserPolicy`, `AttachRolePolicy`, `AttachGroupPolicy`, `PutUserPolicy`, `PutRolePolicy`, `PutGroupPolicy`, `CreatePolicyVersion`, `SetDefaultPolicyVersion`, `AddUserToGroup`

Example triggering context:
```json
{
  "recent_events_60m": [
    {"event_type": "iam:AttachRolePolicy"},
    {"event_type": "iam:AttachRolePolicy"},
    {"event_type": "iam:PutRolePolicy"},
    {"event_type": "iam:PutRolePolicy"},
    {"event_type": "iam:CreatePolicyVersion"}
  ]
}
```

---

### 3. CrossAccountRoleAssumption

| Attribute     | Value                          |
|---------------|--------------------------------|
| `rule_id`     | `cross_account_role_assumption`|
| `rule_name`   | `CrossAccountRoleAssumption`   |
| `severity`    | Moderate                       |
| `confidence`  | 70                             |
| Type          | Single-event                   |

Detects `AssumeRole` calls where the target role belongs to a different AWS account than the calling identity.

Trigger condition: `event_type == "sts:AssumeRole"` AND `extract_account_id(event_parameters.roleArn) != extract_account_id(identity_arn)`

Example triggering event:
```json
{
  "event_type": "sts:AssumeRole",
  "identity_arn": "arn:aws:iam::111111111111:user/alice",
  "event_parameters": {
    "roleArn": "arn:aws:iam::999999999999:role/CrossAccountRole"
  }
}
```

---

### 4. LoggingDisruption

| Attribute     | Value                  |
|---------------|------------------------|
| `rule_id`     | `logging_disruption`   |
| `rule_name`   | `LoggingDisruption`    |
| `severity`    | Critical               |
| `confidence`  | 95                     |
| Type          | Single-event           |

Detects attempts to disable or tamper with AWS logging infrastructure — a common attacker tactic to cover tracks.

Trigger conditions (any of):
`StopLogging`, `DeleteTrail`, `UpdateTrail`, `PutEventSelectors`, `DeleteFlowLogs`, `DeleteLogGroup`, `DeleteLogStream`

Example triggering event:
```json
{
  "event_type": "cloudtrail:StopLogging",
  "identity_arn": "arn:aws:iam::123456789012:user/alice"
}
```

---

### 5. RootUserActivity

| Attribute     | Value                  |
|---------------|------------------------|
| `rule_id`     | `root_user_activity`   |
| `rule_name`   | `RootUserActivity`     |
| `severity`    | Very High              |
| `confidence`  | 100                    |
| Type          | Single-event           |

Detects any API activity performed by the AWS root account. Root usage is almost always anomalous in production environments.

Trigger conditions (in priority order):
1. `identity_type == "Root"` (primary check)
2. `":root"` substring in `identity_arn` (fallback for cases where `identity_type` is not populated)

Example triggering event:
```json
{
  "event_type": "iam:CreateUser",
  "identity_arn": "arn:aws:iam::123456789012:root",
  "identity_type": "Root"
}
```

---

### 6. APIBurstAnomaly

| Attribute     | Value               |
|---------------|---------------------|
| `rule_id`     | `api_burst_anomaly` |
| `rule_name`   | `APIBurstAnomaly`   |
| `severity`    | Moderate            |
| `confidence`  | 65                  |
| Type          | Context-aware       |

Detects an abnormal burst of API calls within a 5-minute window. `recent_events_5m` is derived in-memory from `recent_events_60m` — no additional DynamoDB query.

Trigger condition: `len(context.recent_events_5m) >= 20`

Example triggering context:
```json
{
  "recent_events_60m": [
    20 events all within the last 5 minutes
  ]
}
```

---

### 7. UnusualServiceUsage

| Attribute     | Value                    |
|---------------|--------------------------|
| `rule_id`     | `unusual_service_usage`  |
| `rule_name`   | `UnusualServiceUsage`    |
| `severity`    | Low                      |
| `confidence`  | 60                       |
| Type          | Context-aware            |

Detects first use of a high-risk AWS service in the past 30 days. `prior_services_30d` contains services from events strictly before the current event timestamp, so the current event's service is never pre-included.

High-risk service set: `sts`, `iam`, `organizations`, `kms`, `secretsmanager`, `ssm`

Trigger condition: current event's service prefix is in the high-risk set AND not in `context.prior_services_30d`

Example triggering event (identity has never used `kms` in 30 days):
```json
{
  "event_type": "kms:Decrypt",
  "identity_arn": "arn:aws:iam::123456789012:user/alice"
}
```

---

## Deduplication

Detection_Engine forwards all triggered findings to Incident_Processor without deduplication. Incident_Processor applies a 24-hour deduplication window keyed on `identity_arn` + `detection_type`. This means:

- Multiple firings of the same rule for the same identity within 24 hours produce one Incident record
- Detection_Engine does not need to track state between invocations
- Each Lambda invocation is stateless and independently correct

---

## Rule Summary Table

| rule_id                        | Severity   | Confidence | Type           |
|-------------------------------|------------|------------|----------------|
| `privilege_escalation`         | High       | 80         | Context-aware  |
| `iam_policy_modification_spike`| High       | 75         | Context-aware  |
| `cross_account_role_assumption`| Moderate   | 70         | Single-event   |
| `logging_disruption`           | Critical   | 95         | Single-event   |
| `root_user_activity`           | Very High  | 100        | Single-event   |
| `api_burst_anomaly`            | Moderate   | 65         | Context-aware  |
| `unusual_service_usage`        | Low        | 60         | Context-aware  |
