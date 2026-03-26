# Remediation Workflows

## Table of Contents

- [Risk Modes](#risk-modes)
- [Remediation Actions](#remediation-actions)
- [Safety Controls](#safety-controls)
- [Audit Log Schema](#audit-log-schema)
- [Configuring Rules](#configuring-rules)
- [Operational Runbook](#operational-runbook)

Radius can automatically respond to high-severity incidents by executing approved AWS mutations against the offending IAM identity. This document covers how to configure and operate the remediation system.

---

## Risk Modes

The engine operates in one of three modes. The system ships in `monitor` mode — no mutations are ever performed until an operator explicitly promotes to `alert` or `enforce`.

| Mode | IAM mutations | SNS notification | Audit log |
|---|---|---|---|
| `monitor` | Never | Never | Always |
| `alert` | Never | Always | Always |
| `enforce` | When rules match | Always | Always |

The `dry_run` flag (Lambda environment variable `DRY_RUN=true`, or `"dry_run": true` in the incident payload) overrides any configured mode to `monitor` for that invocation.

### Changing the Risk Mode

```bash
curl -X PUT https://<api-gateway-url>/remediation/config/mode \
  -H "Content-Type: application/json" \
  -d '{"risk_mode": "enforce"}'
```

Valid values: `monitor`, `alert`, `enforce`. Any other value returns HTTP 400.

---

## Remediation Actions

Five actions are available. Each action is idempotent — calling it twice produces the same AWS state.

### `disable_iam_user`

Deactivates all active IAM access keys and deletes the console login profile for the identity.

**Applies to:** `IAMUser` identity type only. Skipped with `outcome=skipped/identity_type_not_supported` for roles or assumed roles.

**AWS API calls:**
- `iam:ListAccessKeys`
- `iam:UpdateAccessKey` (Status → Inactive, for each active key)
- `iam:DeleteLoginProfile` (no-op if no console access exists)

**Rollback procedure:** Re-activate keys individually via the AWS Console or CLI:
```bash
aws iam update-access-key --user-name <username> \
  --access-key-id <key-id> --status Active
aws iam create-login-profile --user-name <username> --password <new-password>
```
The `deactivated_key_ids` list is stored in the audit log `details` field for reference.

---

### `remove_risky_policies`

Identifies and removes managed and inline policies that grant any of the following actions: `iam:*`, `sts:AssumeRole`, `s3:*`, `ec2:*`, `lambda:*`, `organizations:*`.

**Applies to:** IAM users and roles.

**AWS API calls:**
- `iam:ListAttachedUserPolicies` / `iam:ListAttachedRolePolicies`
- `iam:ListUserPolicies` / `iam:ListRolePolicies`
- `iam:GetUserPolicy` / `iam:GetRolePolicy`
- `iam:DetachUserPolicy` / `iam:DetachRolePolicy`
- `iam:DeleteUserPolicy` / `iam:DeleteRolePolicy`

Per-policy failures are non-fatal — the action continues with remaining policies and records each failure in `details.failed`.

**Rollback procedure:** Re-attach or recreate the removed policies. The audit log `details` field contains `removed` (list of policy names/ARNs) and `failed` (list of policies that could not be removed).

---

### `block_role_assumption`

Prepends a `Deny` statement to the IAM role's trust policy, blocking all principals from assuming the role.

**Applies to:** IAM roles only. Skipped with `outcome=skipped/identity_type_not_supported` for users.

**AWS API calls:**
- `iam:GetRole`
- `iam:UpdateAssumeRolePolicy`

The injected statement has `Sid: RadiusBlockAssumption` for easy identification.

**Rollback procedure:** Remove the `RadiusBlockAssumption` statement from the trust policy. The previous trust policy JSON is stored verbatim in the audit log `details.previous_trust_policy` field:
```bash
# Retrieve previous policy from audit log, then:
aws iam update-assume-role-policy --role-name <role-name> \
  --policy-document '<previous_trust_policy_json>'
```

---

### `restrict_network_access`

Attaches an inline deny policy named `RadiusNetworkRestriction` that blocks `ec2:*`, `s3:*`, and `vpc:*` actions from any IP address not in the `allowed_ip_ranges` config list.

**Applies to:** IAM users and roles.

**AWS API calls:**
- `iam:PutUserPolicy` or `iam:PutRolePolicy`

**Rollback procedure:** Delete the inline policy:
```bash
aws iam delete-user-policy --user-name <username> --policy-name RadiusNetworkRestriction
# or for roles:
aws iam delete-role-policy --role-name <role-name> --policy-name RadiusNetworkRestriction
```
The full policy document is stored in the audit log `details.policy_document` field.

---

### `notify_security_team`

Publishes a structured JSON alert to the Remediation SNS topic.

**Applies to:** All identity types.

**Behaviour by mode:**
- `monitor` — suppressed, no publish
- `alert` / `enforce` — publishes to `REMEDIATION_TOPIC_ARN`

**Message fields:** `incident_id`, `identity_arn`, `detection_type`, `severity`, `risk_mode`, `actions_taken`, `timestamp`, `dashboard_link`

**Rollback procedure:** Not applicable — SNS publish is a notification only.

---

## Safety Controls

Before any rule matching occurs, the engine evaluates four guards in order. If any guard fires, the entire evaluation is suppressed and a single audit entry is written with the suppression reason.

| Guard | Config field | Suppression reason |
|---|---|---|
| Excluded ARN | `excluded_arns` (list of ARN strings) | `identity_excluded` |
| Protected account | `protected_account_ids` (list of 12-digit account IDs) | `account_protected` |
| 60-minute cooldown | — (automatic, based on audit log) | `cooldown_active` |
| 24-hour rate limit | — (automatic, max 10 executions per identity) | `rate_limit_exceeded` |

### Configuring Exclusions

```bash
# Add an ARN to the excluded list (full config PUT)
curl -X PUT https://<api-gateway-url>/remediation/config \
  -H "Content-Type: application/json" \
  -d '{
    "excluded_arns": ["arn:aws:iam::123456789012:user/break-glass-admin"],
    "protected_account_ids": ["123456789012"]
  }'
```

---

## Audit Log Schema

Every action evaluation — executed, skipped, suppressed, or failed — writes one record to the `Remediation_Audit_Log` DynamoDB table. A summary record (`action_name=remediation_complete`) is written after all actions complete.

| Field | Type | Description |
|---|---|---|
| `audit_id` | String (UUID v4) | Primary key |
| `incident_id` | String (UUID v4) | Source incident |
| `identity_arn` | String | IAM identity that was evaluated |
| `rule_id` | String | Rule that triggered this action (empty for safety-suppressed and no-match records) |
| `action_name` | String | Action evaluated, or `remediation_suppressed` / `no_rules_matched` / `remediation_complete` |
| `outcome` | String | `executed`, `skipped`, `failed`, `suppressed`, or `summary` |
| `risk_mode` | String | Active mode at evaluation time |
| `dry_run` | Boolean | Whether dry_run was active |
| `timestamp` | String (ISO 8601 UTC) | Evaluation time |
| `details` | String (JSON) | Action-specific metadata (key IDs, policy ARNs, counts) |
| `reason` | String | Suppression or failure reason; empty for executed outcomes |
| `ttl` | Number (Unix timestamp) | Auto-expiry 365 days from write time |

### Querying the Audit Log

```bash
# Last 50 entries
curl https://<api-gateway-url>/remediation/audit

# Filter by incident
curl "https://<api-gateway-url>/remediation/audit?incident_id=<uuid>"

# Filter by identity
curl "https://<api-gateway-url>/remediation/audit?identity_arn=arn:aws:iam::123456789012:user/alice"

# Limit results
curl "https://<api-gateway-url>/remediation/audit?limit=20"
```

---

## Configuring Rules

Rules are stored in the `Remediation_Config` DynamoDB table under the singleton `config_id=global` record.

### Rule Schema

| Field | Type | Description |
|---|---|---|
| `rule_id` | String (UUID v4) | Unique rule identifier |
| `name` | String | Human-readable description |
| `active` | Boolean | Whether the rule participates in matching |
| `priority` | Integer | Lower number = higher priority; rules are evaluated in ascending priority order |
| `min_severity` | String | Minimum incident severity to match: `Low`, `Moderate`, `High`, `Very High`, `Critical` |
| `detection_types` | List\<String\> | Detection types that trigger this rule; empty list matches all |
| `identity_types` | List\<String\> | Identity types this rule applies to; empty list matches all |
| `actions` | List\<String\> | Ordered list of action names to execute |

**Severity ordering:** `Low=1 < Moderate=2 < High=3 < Very High=4 < Critical=5`. A rule with `min_severity=High` matches High, Very High, and Critical incidents.

### Example API Calls

**List current rules:**
```bash
curl https://<api-gateway-url>/remediation/rules
```

**Create a rule — disable compromised users on Critical incidents:**
```bash
curl -X POST https://<api-gateway-url>/remediation/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Disable compromised IAM users on Critical incidents",
    "priority": 1,
    "min_severity": "Critical",
    "detection_types": [],
    "identity_types": ["IAMUser"],
    "actions": ["disable_iam_user", "notify_security_team"]
  }'
```

**Create a rule — block role assumption on cross-account incidents:**
```bash
curl -X POST https://<api-gateway-url>/remediation/rules \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Block role assumption on cross-account incidents",
    "priority": 2,
    "min_severity": "Very High",
    "detection_types": ["cross_account_role_assumption"],
    "identity_types": ["AssumedRole"],
    "actions": ["block_role_assumption", "notify_security_team"]
  }'
```

**Delete (deactivate) a rule:**
```bash
curl -X DELETE https://<api-gateway-url>/remediation/rules/<rule_id>
```

**Get current config (mode + all rules):**
```bash
curl https://<api-gateway-url>/remediation/config
```

---

## Operational Runbook

### Promoting from Monitor to Enforce

1. Review the audit log in monitor mode to confirm rules match the expected incidents
2. Promote to `alert` mode and verify SNS notifications are received correctly
3. Promote to `enforce` mode once alert-mode behaviour is validated

### Responding to an Unexpected Execution

1. Query the audit log for the `incident_id` to see which rules and actions fired
2. Use the `details` field in each audit entry to identify what was changed
3. Follow the rollback procedure for each action (see above)
4. Add the identity ARN to `excluded_arns` if it should not be remediated in future

### Disabling Remediation Immediately

Set the Lambda environment variable `DRY_RUN=true` via the AWS Console or CLI to suppress all mutations without changing the configured risk mode. This takes effect on the next Lambda cold start.
