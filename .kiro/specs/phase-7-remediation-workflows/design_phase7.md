# Design Document — Phase 7: Remediation Workflows and Risk Modes

## Overview

Phase 7 adds a Remediation_Engine Lambda and supporting infrastructure to Radius. When Incident_Processor creates a high-severity incident, it asynchronously invokes Remediation_Engine, which evaluates a configuration-driven rule set and executes approved AWS mutations against the offending IAM identity.

The system is safe by default: it ships in Monitor Mode, where all rules are evaluated and logged but no mutations are performed. Operators promote to Alert Mode (notifications only) or Enforcement Mode (live mutations) through a new API. Every evaluation — executed, skipped, suppressed, or failed — is written to an append-only audit log.

All changes are additive. Existing Lambda handlers, DynamoDB tables, API contracts, and Terraform modules are not modified except for a single async invoke call added to Incident_Processor.

---

## Architecture

### Updated Pipeline

```
Incident_Processor Lambda
    │
    ├── (existing) create_incident() → Incident table
    ├── (existing) publish_alert()   → SNS Alert_Topic
    │
    └── (NEW) invoke_remediation()   → Remediation_Engine Lambda (async, High/Very High/Critical only)
                                              │
                                              ▼
                                    RemediationRuleEngine.evaluate()
                                              │
                                              ├── load_config()         → Remediation_Config table
                                              ├── check_safety_controls()
                                              ├── match_rules()
                                              │
                                              ├── execute_actions()     → IAM / EC2 / VPC APIs
                                              ├── publish_notification() → Remediation_Topic (SNS)
                                              └── write_audit_log()     → Remediation_Audit_Log table
```

### New Components

| Component | Type | Purpose |
|---|---|---|
| Remediation_Engine | Lambda | Evaluates rules, executes actions, writes audit log |
| Remediation_Config | DynamoDB table | Stores Risk_Mode and active rule set |
| Remediation_Audit_Log | DynamoDB table | Append-only audit trail of all evaluations |
| Remediation_Topic | SNS topic | Remediation-specific notifications |

### Directory Structure

```
backend/functions/remediation_engine/
├── handler.py          ← Lambda entry point
├── engine.py           ← RemediationRuleEngine orchestrator
├── config.py           ← Config loading and Risk_Mode management
├── safety.py           ← Cooldown, rate limit, exclusion checks
├── audit.py            ← Audit log writer
├── actions/
│   ├── __init__.py     ← ALL_ACTIONS registry
│   ├── base.py         ← RemediationAction abstract base
│   ├── disable_iam_user.py
│   ├── remove_risky_policies.py
│   ├── block_role_assumption.py
│   ├── restrict_network_access.py
│   └── notify_security_team.py
└── requirements.txt
```

---

## Components and Interfaces

### handler.py

```python
import os
from typing import Any
from backend.functions.remediation_engine.engine import RemediationRuleEngine
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error

_REMEDIATION_CONFIG_TABLE = os.environ["REMEDIATION_CONFIG_TABLE"]
_REMEDIATION_AUDIT_TABLE  = os.environ["REMEDIATION_AUDIT_TABLE"]
_REMEDIATION_TOPIC_ARN    = os.environ["REMEDIATION_TOPIC_ARN"]
_DRY_RUN                  = os.environ.get("DRY_RUN", "false").lower() == "true"

def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Receives an Incident dict from Incident_Processor (async invoke).
    event keys: incident_id, identity_arn, detection_type, severity, confidence,
                status, creation_timestamp, related_event_ids
    Optional: dry_run (bool) — overrides global DRY_RUN env var
    """
    correlation_id = generate_correlation_id()
    dry_run = event.get("dry_run", _DRY_RUN)
    engine = RemediationRuleEngine(
        config_table=_REMEDIATION_CONFIG_TABLE,
        audit_table=_REMEDIATION_AUDIT_TABLE,
        topic_arn=_REMEDIATION_TOPIC_ARN,
        dry_run=dry_run,
        correlation_id=correlation_id,
    )
    return engine.process(event)
```

### engine.py — RemediationRuleEngine

```python
@dataclass
class RemediationResult:
    incident_id: str
    identity_arn: str
    risk_mode: str
    dry_run: bool
    matched_rules: list[str]
    action_outcomes: list[dict]   # [{action, outcome, details}]
    executed: int
    skipped: int
    failed: int
    suppressed: int

class RemediationRuleEngine:
    def process(self, incident: dict) -> dict:
        # 1. Load config (Risk_Mode + rules)
        config = load_config(self.config_table)
        risk_mode = "monitor" if self.dry_run else config["risk_mode"]

        # 2. Safety controls (exclusions, cooldown, rate limit)
        suppression = check_safety_controls(
            incident["identity_arn"], config, self.audit_table
        )
        if suppression:
            write_audit_suppressed(self.audit_table, incident, suppression, risk_mode, self.dry_run)
            return _result(suppressed=True)

        # 3. Match rules
        matched = match_rules(config["rules"], incident)
        if not matched:
            write_audit_no_match(self.audit_table, incident, risk_mode, self.dry_run)
            return _result(matched=[])

        # 4. Collect unique actions from all matched rules
        actions = deduplicate_actions([a for rule in matched for a in rule["actions"]])

        # 5. Execute or suppress each action
        outcomes = []
        for action_name in actions:
            action = get_action(action_name)
            if risk_mode == "monitor":
                outcome = action.suppress(incident, "monitor_mode")
            else:
                outcome = action.execute(incident)
            write_audit_entry(self.audit_table, incident, rule_id, action_name, outcome, risk_mode, self.dry_run)
            outcomes.append(outcome)

        # 6. Notify (alert + enforce modes only)
        if risk_mode in ("alert", "enforce"):
            notify(self.topic_arn, incident, risk_mode, outcomes)

        # 7. Summary audit record
        write_audit_summary(self.audit_table, incident, outcomes, risk_mode, self.dry_run)

        return _build_result(incident, risk_mode, matched, outcomes, self.dry_run)
```

### actions/base.py

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ActionOutcome:
    action_name: str
    outcome: str          # executed | skipped | failed | suppressed
    reason: str | None    # populated for skipped/suppressed/failed
    details: dict         # action-specific metadata (key IDs, policy ARNs, etc.)

class RemediationAction(ABC):
    action_name: str

    @abstractmethod
    def execute(self, incident: dict) -> ActionOutcome:
        """Execute the action against the identity. Must be idempotent."""

    def suppress(self, incident: dict, reason: str) -> ActionOutcome:
        return ActionOutcome(
            action_name=self.action_name,
            outcome="suppressed",
            reason=reason,
            details={},
        )
```

### actions/disable_iam_user.py

```python
class DisableIAMUserAction(RemediationAction):
    action_name = "disable_iam_user"

    def execute(self, incident: dict) -> ActionOutcome:
        identity_arn = incident["identity_arn"]
        # Only applies to IAMUser identity type
        if not _is_iam_user(identity_arn):
            return ActionOutcome(action_name=self.action_name, outcome="skipped",
                                 reason="identity_type_not_supported", details={})
        username = _extract_username(identity_arn)
        iam = boto3.client("iam")
        deactivated_keys = []
        try:
            # Deactivate all active access keys
            keys = iam.list_access_keys(UserName=username)["AccessKeyMetadata"]
            for key in keys:
                if key["Status"] == "Active":
                    iam.update_access_key(UserName=username,
                                          AccessKeyId=key["AccessKeyId"],
                                          Status="Inactive")
                    deactivated_keys.append(key["AccessKeyId"])
            # Disable console login (delete login profile if exists)
            try:
                iam.delete_login_profile(UserName=username)
            except iam.exceptions.NoSuchEntityException:
                pass  # No console access — nothing to disable
        except Exception as exc:
            return ActionOutcome(action_name=self.action_name, outcome="failed",
                                 reason=str(exc), details={})
        return ActionOutcome(action_name=self.action_name, outcome="executed",
                             reason=None, details={"deactivated_key_ids": deactivated_keys})
```

### actions/remove_risky_policies.py

```python
_RISKY_ACTIONS = {"iam:*", "sts:AssumeRole", "s3:*", "ec2:*", "lambda:*", "organizations:*"}

class RemoveRiskyPoliciesAction(RemediationAction):
    action_name = "remove_risky_policies"

    def execute(self, incident: dict) -> ActionOutcome:
        identity_arn = incident["identity_arn"]
        iam = boto3.client("iam")
        removed, failed = [], []
        # Detect identity type and call appropriate IAM APIs
        # Detach managed policies, delete inline policies containing risky actions
        ...
        if not removed and not failed:
            return ActionOutcome(action_name=self.action_name, outcome="skipped",
                                 reason="no_risky_policies_found", details={})
        return ActionOutcome(action_name=self.action_name, outcome="executed",
                             reason=None, details={"removed": removed, "failed": failed})
```

### actions/block_role_assumption.py

```python
class BlockRoleAssumptionAction(RemediationAction):
    action_name = "block_role_assumption"

    def execute(self, incident: dict) -> ActionOutcome:
        identity_arn = incident["identity_arn"]
        if not _is_iam_role(identity_arn):
            return ActionOutcome(action_name=self.action_name, outcome="skipped",
                                 reason="identity_type_not_supported", details={})
        role_name = _extract_role_name(identity_arn)
        iam = boto3.client("iam")
        try:
            current_policy = iam.get_role(RoleName=role_name)["Role"]["AssumeRolePolicyDocument"]
            deny_statement = {
                "Sid": "RadiusBlockAssumption",
                "Effect": "Deny",
                "Principal": "*",
                "Action": "sts:AssumeRole",
            }
            new_policy = dict(current_policy)
            new_policy["Statement"] = [deny_statement] + current_policy.get("Statement", [])
            iam.update_assume_role_policy(RoleName=role_name,
                                          PolicyDocument=json.dumps(new_policy))
        except Exception as exc:
            return ActionOutcome(action_name=self.action_name, outcome="failed",
                                 reason=str(exc), details={})
        return ActionOutcome(action_name=self.action_name, outcome="executed",
                             reason=None,
                             details={"previous_trust_policy": json.dumps(current_policy)})
```

### actions/restrict_network_access.py

```python
_POLICY_NAME = "RadiusNetworkRestriction"

class RestrictNetworkAccessAction(RemediationAction):
    action_name = "restrict_network_access"

    def execute(self, incident: dict) -> ActionOutcome:
        identity_arn = incident["identity_arn"]
        allowed_ips = _load_allowed_ips()  # from Remediation_Config
        deny_policy = {
            "Version": "2012-10-17",
            "Statement": [{
                "Sid": "RadiusDenyNetworkActions",
                "Effect": "Deny",
                "Action": ["ec2:*", "s3:*", "vpc:*"],
                "Resource": "*",
                "Condition": {
                    "NotIpAddress": {"aws:SourceIp": allowed_ips}
                }
            }]
        }
        iam = boto3.client("iam")
        try:
            if _is_iam_user(identity_arn):
                iam.put_user_policy(UserName=_extract_username(identity_arn),
                                    PolicyName=_POLICY_NAME,
                                    PolicyDocument=json.dumps(deny_policy))
            elif _is_iam_role(identity_arn):
                iam.put_role_policy(RoleName=_extract_role_name(identity_arn),
                                    PolicyName=_POLICY_NAME,
                                    PolicyDocument=json.dumps(deny_policy))
        except Exception as exc:
            return ActionOutcome(action_name=self.action_name, outcome="failed",
                                 reason=str(exc), details={})
        return ActionOutcome(action_name=self.action_name, outcome="executed",
                             reason=None, details={"policy_document": json.dumps(deny_policy)})
```

### config.py

```python
def load_config(config_table: str) -> dict:
    """Load Risk_Mode and active rules from Remediation_Config table."""
    item = get_item(config_table, {"config_id": "global"})
    if item is None:
        return {"risk_mode": "monitor", "rules": [], "excluded_arns": [],
                "protected_account_ids": [], "allowed_ip_ranges": []}
    return item

def update_risk_mode(config_table: str, new_mode: str) -> None:
    _VALID_MODES = {"monitor", "alert", "enforce"}
    if new_mode not in _VALID_MODES:
        raise ValidationError(f"Invalid risk_mode: {new_mode!r}")
    update_item(config_table, key={"config_id": "global"},
                update_expression="SET risk_mode = :mode",
                expression_attribute_values={":mode": new_mode})
```

### safety.py

```python
def check_safety_controls(
    identity_arn: str,
    config: dict,
    audit_table: str,
) -> str | None:
    """
    Returns a suppression reason string if the identity should be suppressed,
    or None if processing should continue.

    Checks (in order):
    1. excluded_arns list
    2. protected_account_ids list
    3. 60-minute cooldown (query audit log for recent executions)
    4. 24-hour rate limit (max 10 executions)
    """
    account_id = _extract_account_id(identity_arn)

    if identity_arn in config.get("excluded_arns", []):
        return "identity_excluded"
    if account_id in config.get("protected_account_ids", []):
        return "account_protected"

    recent = _query_recent_executions(audit_table, identity_arn, hours=1)
    if recent:
        return "cooldown_active"

    daily = _query_recent_executions(audit_table, identity_arn, hours=24)
    if len(daily) >= 10:
        return "rate_limit_exceeded"

    return None
```

### audit.py

```python
def write_audit_entry(
    audit_table: str,
    incident: dict,
    rule_id: str,
    action_name: str,
    outcome: ActionOutcome,
    risk_mode: str,
    dry_run: bool,
) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    record = {
        "audit_id": str(uuid.uuid4()),
        "incident_id": incident["incident_id"],
        "identity_arn": incident["identity_arn"],
        "rule_id": rule_id,
        "action_name": action_name,
        "outcome": outcome.outcome,
        "risk_mode": risk_mode,
        "dry_run": dry_run,
        "timestamp": now,
        "details": json.dumps(outcome.details),
        "reason": outcome.reason or "",
        "ttl": int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp()),
    }
    put_item(audit_table, record)
```

---

## Data Models

### Remediation_Config Table

```
PK: config_id (String)  — always "global" for the singleton config record
```

**Config record shape:**
```json
{
  "config_id": "global",
  "risk_mode": "monitor",
  "rules": [
    {
      "rule_id": "uuid-v4",
      "name": "Disable compromised users on Critical incidents",
      "active": true,
      "priority": 1,
      "min_severity": "Critical",
      "detection_types": [],
      "identity_types": ["IAMUser"],
      "actions": ["disable_iam_user", "notify_security_team"]
    }
  ],
  "excluded_arns": [],
  "protected_account_ids": [],
  "allowed_ip_ranges": ["10.0.0.0/8"]
}
```

### Remediation_Audit_Log Table

```
PK: audit_id (String — UUID v4)
GSIs:
  IdentityTimeIndex  — PK: identity_arn, SK: timestamp (ALL)
  IncidentIndex      — PK: incident_id, SK: timestamp (KEYS_ONLY)
TTL attribute: ttl (365 days)
```

**Audit record shape:**
```json
{
  "audit_id": "uuid-v4",
  "incident_id": "uuid-v4",
  "identity_arn": "arn:aws:iam::123456789012:user/alice",
  "rule_id": "uuid-v4",
  "action_name": "disable_iam_user",
  "outcome": "executed",
  "risk_mode": "enforce",
  "dry_run": false,
  "timestamp": "2026-03-16T10:00:00.000000+00:00",
  "details": "{\"deactivated_key_ids\": [\"AKIAIOSFODNN7EXAMPLE\"]}",
  "reason": "",
  "ttl": 1773993600
}
```

### Remediation Rule Shape

```json
{
  "rule_id": "uuid-v4",
  "name": "string",
  "active": true,
  "priority": 1,
  "min_severity": "High",
  "detection_types": ["privilege_escalation", "logging_disruption"],
  "identity_types": ["IAMUser", "AssumedRole"],
  "actions": ["disable_iam_user", "notify_security_team"]
}
```

**Severity ordering for `min_severity` matching:**
```
Low=1, Moderate=2, High=3, Very High=4, Critical=5
```

A rule matches when `severity_rank(incident.severity) >= severity_rank(rule.min_severity)`.

---

## Incident_Processor Integration

The only change to existing code is a single async invoke call added to `incident_processor/processor.py`:

```python
# In create_incident(), after put_item():
def _invoke_remediation(incident: dict, remediation_lambda_arn: str) -> None:
    """Asynchronously invoke Remediation_Engine. Non-fatal on failure."""
    if not remediation_lambda_arn:
        return
    try:
        lambda_client = boto3.client("lambda")
        lambda_client.invoke(
            FunctionName=remediation_lambda_arn,
            InvocationType="Event",   # async
            Payload=json.dumps(incident).encode(),
        )
    except Exception as exc:
        logger.warning("Remediation_Engine invoke failed (non-fatal)", extra={"error": str(exc)})
```

This is called from `create_incident()` only when `incident["severity"]` is in `{"High", "Very High", "Critical"}`. The `REMEDIATION_LAMBDA_ARN` environment variable is optional — if absent, the call is skipped, preserving backward compatibility.

---

## API Endpoints

New routes added to `api_handler/handler.py` route table:

| Method | Resource | Handler | Description |
|---|---|---|---|
| GET | `/remediation/config` | `get_remediation_config` | Returns Risk_Mode + active rules |
| PUT | `/remediation/config/mode` | `put_remediation_mode` | Updates Risk_Mode |
| GET | `/remediation/rules` | `list_remediation_rules` | Returns rules ordered by priority |
| POST | `/remediation/rules` | `create_remediation_rule` | Creates a new rule |
| DELETE | `/remediation/rules/{rule_id}` | `delete_remediation_rule` | Deactivates a rule |
| GET | `/remediation/audit` | `list_remediation_audit` | Returns last 50 audit entries |

**GET /remediation/config response:**
```json
{
  "risk_mode": "monitor",
  "rules": [...],
  "excluded_arns": [],
  "protected_account_ids": []
}
```

**PUT /remediation/config/mode request body:**
```json
{ "risk_mode": "enforce" }
```

**POST /remediation/rules request body:**
```json
{
  "name": "Block role assumption on Very High incidents",
  "priority": 2,
  "min_severity": "Very High",
  "detection_types": ["cross_account_role_assumption"],
  "identity_types": ["AssumedRole"],
  "actions": ["block_role_assumption", "notify_security_team"]
}
```

**GET /remediation/audit query parameters:**
- `incident_id` (optional) — filter by incident
- `identity_arn` (optional) — filter by identity
- `limit` (optional, default 50, max 100)

---

## Terraform Changes

### New Resources

```hcl
# infra/modules/dynamodb/main.tf — two new tables

resource "aws_dynamodb_table" "remediation_config" {
  name         = "${var.env}-remediation-config"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "config_id"
  attribute { name = "config_id" type = "S" }
  server_side_encryption { enabled = true; kms_master_key_id = var.kms_key_arn }
  point_in_time_recovery { enabled = true }
}

resource "aws_dynamodb_table" "remediation_audit_log" {
  name         = "${var.env}-remediation-audit-log"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "audit_id"
  attribute { name = "audit_id"      type = "S" }
  attribute { name = "identity_arn"  type = "S" }
  attribute { name = "incident_id"   type = "S" }
  attribute { name = "timestamp"     type = "S" }

  global_secondary_index {
    name            = "IdentityTimeIndex"
    hash_key        = "identity_arn"
    range_key       = "timestamp"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "IncidentIndex"
    hash_key        = "incident_id"
    range_key       = "timestamp"
    projection_type = "KEYS_ONLY"
  }
  ttl { attribute_name = "ttl" enabled = true }
  server_side_encryption { enabled = true; kms_master_key_id = var.kms_key_arn }
  point_in_time_recovery { enabled = true }
}

# infra/modules/sns/main.tf — new Remediation_Topic
resource "aws_sns_topic" "remediation_topic" {
  name              = "${var.env}-radius-remediation"
  kms_master_key_id = var.kms_key_arn
}

# infra/modules/lambda/main.tf — new Remediation_Engine function
resource "aws_lambda_function" "remediation_engine" {
  function_name = "${var.env}-remediation-engine"
  runtime       = "python3.12"
  architectures = ["arm64"]
  timeout       = 60
  environment {
    variables = {
      REMEDIATION_CONFIG_TABLE = aws_dynamodb_table.remediation_config.name
      REMEDIATION_AUDIT_TABLE  = aws_dynamodb_table.remediation_audit_log.name
      REMEDIATION_TOPIC_ARN    = aws_sns_topic.remediation_topic.arn
      DRY_RUN                  = "false"
    }
  }
}
```

### IAM Permissions for Remediation_Engine

The Remediation_Engine Lambda role requires:
- `iam:ListAccessKeys`, `iam:UpdateAccessKey`, `iam:DeleteLoginProfile` — for disable_iam_user
- `iam:ListAttachedUserPolicies`, `iam:ListAttachedRolePolicies`, `iam:ListUserPolicies`, `iam:ListRolePolicies`, `iam:GetUserPolicy`, `iam:GetRolePolicy`, `iam:DetachUserPolicy`, `iam:DetachRolePolicy`, `iam:DeleteUserPolicy`, `iam:DeleteRolePolicy` — for remove_risky_policies
- `iam:GetRole`, `iam:UpdateAssumeRolePolicy` — for block_role_assumption
- `iam:PutUserPolicy`, `iam:PutRolePolicy` — for restrict_network_access
- `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query` — on Remediation_Config and Remediation_Audit_Log tables
- `sns:Publish` — on Remediation_Topic

---

## Correctness Properties

### Property 1: Rule Serialization Round-Trip

For any valid remediation rule configuration, serializing the rule to JSON and deserializing it produces an equivalent rule object with identical field values.

**Validates: Requirement 12.1**

### Property 2: Idempotency Under Cooldown

For any valid Incident payload, invoking Remediation_Engine twice with the same payload and the same Risk_Mode produces `outcome = suppressed` with `reason = cooldown_active` for all actions on the second invocation.

**Validates: Requirement 12.2, 11.1**

### Property 3: Deterministic Rule Matching

For any Incident and rule configuration, the set of matched rules is determined solely by the Incident's `severity`, `detection_type`, and the identity's `identity_type`. The same inputs always produce the same matched rule set.

**Validates: Requirement 12.3**

### Property 4: Audit ID Validity

For all audit log entries written by Remediation_Engine, the `audit_id` field is a valid UUID v4 string.

**Validates: Requirement 12.4**

### Property 5: Monitor Mode Suppression

For any Incident and any rule configuration, when Risk_Mode is `monitor` or `dry_run` is `true`, all action outcomes in the audit log have `outcome = suppressed` and no AWS IAM or SNS API calls are made.

**Validates: Requirements 1.2, 1.7, 12.5**

### Property 6: Severity Ordering Invariant

For any two severity levels A and B where A ranks higher than B in the ordering (Low < Moderate < High < Very High < Critical), a rule with `min_severity = B` matches all incidents that a rule with `min_severity = A` matches, plus additional incidents at severity B.

**Validates: Requirement 2.4**

### Property 7: Audit Log Completeness

For any Incident processed by Remediation_Engine, the total count of audit entries written equals the number of matched actions plus one summary record, regardless of individual action outcomes.

**Validates: Requirement 8.5**

---

## Error Handling

### Action Failure Isolation

Each action is executed in an independent try/except block. A failure in one action (e.g. IAM API throttling) does not prevent subsequent actions from executing. All failures are recorded in the audit log with `outcome = failed` and the error message in `reason`.

### Lambda Timeout Safety

Audit log writes use the existing `put_item` with retry logic from `dynamodb_utils.py`. The summary audit record is written last, after all actions complete. If Lambda times out mid-execution, partial audit records are preserved — the absence of a summary record indicates incomplete processing.

### Backward Compatibility

The `REMEDIATION_LAMBDA_ARN` environment variable on Incident_Processor is optional. If not set, `_invoke_remediation()` returns immediately without error. This means existing deployments continue to work without the new Lambda deployed.

---

## Testing Strategy

### Unit Tests

```
backend/tests/
├── test_remediation_engine.py       ← rule matching, action dispatch, mode behaviour
├── test_remediation_actions.py      ← per-action unit tests with mocked IAM client
├── test_remediation_safety.py       ← cooldown, rate limit, exclusion logic
└── test_remediation_config.py       ← config load/update, risk mode validation
```

### Integration Tests

```
backend/tests/integration/
└── test_remediation_integration.py  ← full engine with moto (DynamoDB + SNS + IAM)
```

Key integration test scenarios:
- Monitor mode: all actions suppressed, audit entries written
- Alert mode: SNS published, no IAM mutations
- Enforcement mode: IAM mutations executed, SNS published, audit entries written
- Cooldown: second invocation suppressed within 60 minutes
- Exclusion: excluded ARN suppressed at all modes
- Dry run: suppressed regardless of configured mode

### Property-Based Tests

```
backend/tests/test_remediation_properties.py
```

Covers Properties 1–7 using Hypothesis strategies for generating valid Incident dicts and rule configurations.
