# Requirements Document — Phase 7: Remediation Workflows and Risk Modes

## Introduction

Phase 7 adds automated remediation capabilities to Radius. When an IAM identity reaches a dangerous risk level, operators can configure Radius to respond automatically — disabling users, removing risky policies, blocking role assumption, restricting network access, or notifying security teams.

Remediation is optional and safe by default. The system ships in Monitor Mode, where all actions are evaluated and logged but never executed. Operators must explicitly promote to Alert Mode (notifications only) or Enforcement Mode (live AWS mutations) through configuration. Every remediation action — whether executed or suppressed — is written to an immutable audit log.

All work is additive. No existing Lambda handler signatures, DynamoDB table definitions, API contracts, or Terraform module interfaces are modified.

---

## Glossary

- **Remediation_Engine**: Lambda function that evaluates remediation rules against an Incident and executes approved actions.
- **Remediation_Rule**: A configuration-driven rule that maps a trigger condition (identity type, severity, detection type) to one or more remediation actions.
- **Remediation_Action**: A discrete, reversible AWS mutation performed against an IAM identity (e.g. disable user, detach policy).
- **Remediation_Config**: DynamoDB table storing the active remediation rule set and the current Risk_Mode.
- **Remediation_Audit_Log**: DynamoDB table storing an immutable record of every remediation evaluation and execution.
- **Risk_Mode**: The global operating mode of the remediation system. One of `monitor`, `alert`, or `enforce`.
- **Monitor_Mode**: Risk_Mode in which all remediation rules are evaluated and logged but no AWS mutations are performed and no notifications are sent.
- **Alert_Mode**: Risk_Mode in which all remediation rules are evaluated, notifications are sent for matched rules, but no AWS mutations are performed.
- **Enforcement_Mode**: Risk_Mode in which all remediation rules are evaluated, notifications are sent, and approved AWS mutations are executed.
- **Dry_Run**: A per-invocation flag that forces Monitor_Mode behaviour regardless of the global Risk_Mode setting.
- **Incident**: DynamoDB table storing security incidents produced by Incident_Processor (existing).
- **Identity_Profile**: DynamoDB table storing IAM identity metadata (existing).
- **SNS Alert_Topic**: Existing SNS topic used for high-severity incident alerts.
- **Remediation_Topic**: New SNS topic used exclusively for remediation notifications.
- **Safe_Action**: A remediation action that is reversible and has a documented rollback procedure.
- **Blast_Radius_Score**: DynamoDB table storing the current score snapshot per identity (existing).

---

## Requirements

### Requirement 1: Risk Mode Configuration

**User Story:** As a security operator, I want to configure the global risk mode, so that I can control whether Radius monitors, alerts, or enforces remediation actions across my environment.

#### Acceptance Criteria

1. THE Remediation_Config table SHALL store exactly one active Risk_Mode record with a value of `monitor`, `alert`, or `enforce`.
2. WHEN the Risk_Mode is set to `monitor`, THE Remediation_Engine SHALL evaluate all matching rules and write audit log entries but SHALL NOT execute any AWS mutations or publish any SNS notifications.
3. WHEN the Risk_Mode is set to `alert`, THE Remediation_Engine SHALL evaluate all matching rules, publish SNS notifications for matched rules, and write audit log entries but SHALL NOT execute any AWS mutations.
4. WHEN the Risk_Mode is set to `enforce`, THE Remediation_Engine SHALL evaluate all matching rules, execute approved AWS mutations, publish SNS notifications, and write audit log entries.
5. THE Remediation_Config table SHALL default to `monitor` Risk_Mode on first deployment.
6. WHEN an operator updates the Risk_Mode via the API, THE API_Handler SHALL validate that the new value is one of `monitor`, `alert`, or `enforce` and reject any other value with a 400 response.
7. WHEN a Dry_Run flag is set to `true` in the invocation payload, THE Remediation_Engine SHALL behave as if the Risk_Mode is `monitor` regardless of the configured Risk_Mode.

---

### Requirement 2: Remediation Rule Engine

**User Story:** As a security operator, I want to define remediation rules that map threat conditions to response actions, so that the system can automatically respond to dangerous identities.

#### Acceptance Criteria

1. THE Remediation_Engine SHALL evaluate all active remediation rules against an Incident when invoked.
2. WHEN a remediation rule is evaluated, THE Remediation_Engine SHALL match the rule against the Incident's `severity`, `detection_type`, and the associated identity's `identity_type`.
3. THE Remediation_Rule SHALL support the following match fields: `min_severity` (one of `Low`, `Moderate`, `High`, `Very High`, `Critical`), `detection_types` (list of detection type strings, empty list means match all), and `identity_types` (list of identity type strings, empty list means match all).
4. WHEN a rule's `min_severity` is set, THE Remediation_Engine SHALL match only Incidents whose severity is greater than or equal to the configured minimum severity according to the severity ordering: Low < Moderate < High < Very High < Critical.
5. THE Remediation_Rule SHALL specify one or more actions from the set: `disable_iam_user`, `remove_risky_policies`, `block_role_assumption`, `restrict_network_access`, `notify_security_team`.
6. WHEN multiple rules match a single Incident, THE Remediation_Engine SHALL execute all matched rules' actions without duplication.
7. IF no rules match an Incident, THEN THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `no_match` and return without performing any actions.
8. THE Remediation_Engine SHALL process rules in priority order, where lower `priority` integer values are evaluated first.

---

### Requirement 3: Disable IAM User Action

**User Story:** As a security operator, I want Radius to disable a compromised IAM user, so that the identity cannot perform further API calls while an investigation is underway.

#### Acceptance Criteria

1. WHEN the `disable_iam_user` action is triggered for an IAM user identity, THE Remediation_Engine SHALL call `iam:UpdateLoginProfile` to disable console access and `iam:UpdateAccessKey` to deactivate all active access keys for that user.
2. WHEN the `disable_iam_user` action is triggered for a non-IAM-user identity type (e.g. `AssumedRole`, `AWSService`), THE Remediation_Engine SHALL skip the action and write an audit log entry with `outcome` equal to `skipped` and `reason` equal to `identity_type_not_supported`.
3. WHEN the `disable_iam_user` action completes successfully, THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `executed` and include the list of deactivated access key IDs.
4. IF the `disable_iam_user` action fails due to an AWS API error, THEN THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `failed`, include the error message, and continue processing remaining actions without raising an unhandled exception.
5. THE `disable_iam_user` action SHALL be classified as a Safe_Action with a documented rollback procedure: re-enable login profile and reactivate access keys using the stored key IDs from the audit log.

---

### Requirement 4: Remove Risky Policies Action

**User Story:** As a security operator, I want Radius to remove overly permissive policies from a compromised identity, so that the identity's blast radius is reduced immediately.

#### Acceptance Criteria

1. WHEN the `remove_risky_policies` action is triggered, THE Remediation_Engine SHALL identify all inline and managed policies attached to the identity that contain any of the following high-risk actions: `iam:*`, `sts:AssumeRole`, `s3:*`, `ec2:*`, `lambda:*`, `organizations:*`.
2. WHEN risky policies are identified, THE Remediation_Engine SHALL detach managed policies using `iam:DetachUserPolicy` or `iam:DetachRolePolicy` and delete inline policies using `iam:DeleteUserPolicy` or `iam:DeleteRolePolicy`.
3. WHEN the `remove_risky_policies` action completes, THE Remediation_Engine SHALL write an audit log entry listing all removed policy ARNs and inline policy names.
4. IF no risky policies are found for the identity, THEN THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `skipped` and `reason` equal to `no_risky_policies_found`.
5. IF the `remove_risky_policies` action fails for any individual policy, THEN THE Remediation_Engine SHALL log the failure for that policy, continue attempting to remove remaining policies, and record all successes and failures in the audit log entry.

---

### Requirement 5: Block Role Assumption Action

**User Story:** As a security operator, I want Radius to block a role from being assumed, so that lateral movement via role chaining is stopped immediately.

#### Acceptance Criteria

1. WHEN the `block_role_assumption` action is triggered for an IAM role identity, THE Remediation_Engine SHALL update the role's trust policy to add a `Deny` statement for `sts:AssumeRole` with a condition that applies to all principals.
2. WHEN the `block_role_assumption` action is triggered for a non-role identity type, THE Remediation_Engine SHALL skip the action and write an audit log entry with `outcome` equal to `skipped` and `reason` equal to `identity_type_not_supported`.
3. WHEN the `block_role_assumption` action completes successfully, THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `executed` and include the previous trust policy document as a JSON string for rollback purposes.
4. IF the `block_role_assumption` action fails due to an AWS API error, THEN THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `failed`, include the error message, and continue processing remaining actions.
5. THE `block_role_assumption` action SHALL be classified as a Safe_Action with a documented rollback procedure: restore the previous trust policy document stored in the audit log entry.

---

### Requirement 6: Restrict Network Access Action

**User Story:** As a security operator, I want Radius to restrict network access for a compromised identity, so that exfiltration paths are closed while the incident is investigated.

#### Acceptance Criteria

1. WHEN the `restrict_network_access` action is triggered, THE Remediation_Engine SHALL attach an IAM deny policy to the identity that denies all `ec2:*`, `s3:*`, and `vpc:*` actions from any source IP address not in the configured `allowed_ip_ranges` list.
2. THE `restrict_network_access` action SHALL attach the deny policy as an inline policy named `RadiusNetworkRestriction` to avoid conflicts with existing managed policies.
3. WHEN the `restrict_network_access` action completes successfully, THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `executed` and include the full policy document applied.
4. IF the `restrict_network_access` action fails due to an AWS API error, THEN THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `failed`, include the error message, and continue processing remaining actions.
5. THE `restrict_network_access` action SHALL be classified as a Safe_Action with a documented rollback procedure: delete the `RadiusNetworkRestriction` inline policy.

---

### Requirement 7: Notify Security Team Action

**User Story:** As a security operator, I want Radius to notify my security team when a remediation rule fires, so that human responders are aware of automated actions taken.

#### Acceptance Criteria

1. WHEN the `notify_security_team` action is triggered, THE Remediation_Engine SHALL publish a structured JSON message to the Remediation_Topic SNS topic.
2. THE notification message SHALL include: `incident_id`, `identity_arn`, `detection_type`, `severity`, `risk_mode`, `actions_taken` (list of action names and outcomes), `timestamp`, and a `dashboard_link` to the incident detail page.
3. WHEN the Risk_Mode is `monitor`, THE Remediation_Engine SHALL NOT publish any SNS notification even if `notify_security_team` is listed as an action in a matched rule.
4. WHEN the Risk_Mode is `alert` or `enforce`, THE Remediation_Engine SHALL publish the notification regardless of whether other actions were executed or skipped.
5. IF the SNS publish call fails, THEN THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `failed` for the notify action, log the error, and continue without raising an unhandled exception.

---

### Requirement 8: Remediation Audit Log

**User Story:** As a security auditor, I want an immutable record of every remediation evaluation and action, so that I can demonstrate compliance and investigate the impact of automated responses.

#### Acceptance Criteria

1. THE Remediation_Audit_Log table SHALL store one record per remediation action evaluation with fields: `audit_id` (UUID v4), `incident_id`, `identity_arn`, `rule_id`, `action_name`, `outcome` (one of `executed`, `skipped`, `failed`, `suppressed`), `risk_mode`, `dry_run`, `timestamp`, `details` (JSON string), and `ttl`.
2. WHEN an action is suppressed due to Monitor_Mode or Dry_Run, THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `suppressed`.
3. THE Remediation_Audit_Log table SHALL use a TTL of 365 days from the `timestamp` field.
4. THE Remediation_Audit_Log table SHALL be append-only — no update or delete operations SHALL be performed on existing audit records.
5. WHEN the Remediation_Engine completes processing an Incident, THE Remediation_Engine SHALL write a summary audit record with `action_name` equal to `remediation_complete`, listing the total count of executed, skipped, failed, and suppressed actions.
6. FOR ALL audit log writes, THE Remediation_Engine SHALL ensure the write completes before returning a response, so that no audit record is lost on Lambda timeout.

---

### Requirement 9: Remediation Lambda Integration

**User Story:** As a developer, I want the Remediation_Engine to be invoked automatically when a high-severity incident is created, so that remediation begins without manual intervention.

#### Acceptance Criteria

1. WHEN Incident_Processor creates a new Incident with severity `High`, `Very High`, or `Critical`, THE Incident_Processor SHALL asynchronously invoke the Remediation_Engine Lambda with the full Incident record as the payload.
2. WHEN Incident_Processor deduplicates an Incident (appends to existing), THE Incident_Processor SHALL NOT invoke the Remediation_Engine again for the same incident.
3. THE Remediation_Engine Lambda SHALL be idempotent — invoking it twice with the same Incident payload SHALL produce the same audit log outcome without duplicating AWS mutations.
4. THE Remediation_Engine Lambda SHALL complete all processing within 60 seconds to stay within Lambda timeout constraints.
5. IF the Remediation_Engine Lambda invocation fails (Lambda error or timeout), THEN THE Incident_Processor SHALL log the failure as a non-fatal error and continue normal incident processing.

---

### Requirement 10: Configuration API

**User Story:** As a security operator, I want API endpoints to manage remediation rules and risk mode, so that I can configure the system without direct database access.

#### Acceptance Criteria

1. THE API_Handler SHALL expose a `GET /remediation/config` endpoint that returns the current Risk_Mode and the list of active remediation rules.
2. THE API_Handler SHALL expose a `PUT /remediation/config/mode` endpoint that accepts a JSON body with a `risk_mode` field and updates the global Risk_Mode.
3. THE API_Handler SHALL expose a `GET /remediation/rules` endpoint that returns all configured remediation rules ordered by `priority`.
4. THE API_Handler SHALL expose a `POST /remediation/rules` endpoint that creates a new remediation rule and returns the created rule with a generated `rule_id`.
5. THE API_Handler SHALL expose a `DELETE /remediation/rules/{rule_id}` endpoint that deactivates a remediation rule by setting its `active` field to `false`.
6. THE API_Handler SHALL expose a `GET /remediation/audit` endpoint that returns the most recent 50 audit log entries, with optional filtering by `incident_id` and `identity_arn` query parameters.
7. WHEN a `POST /remediation/rules` request is received with an invalid action name, THE API_Handler SHALL return a 400 response listing the invalid action names.

---

### Requirement 11: Remediation Safety Controls

**User Story:** As a security operator, I want safety controls that prevent accidental or runaway remediation, so that automated actions do not cause unintended outages.

#### Acceptance Criteria

1. THE Remediation_Engine SHALL maintain a per-identity cooldown period of 60 minutes — if a remediation action was executed for an identity within the last 60 minutes, THE Remediation_Engine SHALL skip all actions for that identity and write an audit log entry with `outcome` equal to `suppressed` and `reason` equal to `cooldown_active`.
2. THE Remediation_Engine SHALL enforce a maximum of 10 remediation executions per identity per 24-hour rolling window — if this limit is exceeded, THE Remediation_Engine SHALL suppress all actions and write an audit log entry with `outcome` equal to `suppressed` and `reason` equal to `rate_limit_exceeded`.
3. THE Remediation_Config table SHALL support an `excluded_arns` list — identities whose ARNs appear in this list SHALL never be subject to automated remediation actions.
4. WHEN an identity ARN matches the `excluded_arns` list, THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `suppressed` and `reason` equal to `identity_excluded`.
5. THE Remediation_Config table SHALL support a `protected_account_ids` list — identities in these AWS accounts SHALL never be subject to automated remediation actions.
6. WHEN an identity belongs to a protected account, THE Remediation_Engine SHALL write an audit log entry with `outcome` equal to `suppressed` and `reason` equal to `account_protected`.

---

### Requirement 12: Remediation Round-Trip and Idempotency

**User Story:** As a developer, I want the remediation system to be testable and idempotent, so that I can verify correctness and safely retry failed invocations.

#### Acceptance Criteria

1. FOR ALL remediation rule configurations, serializing a rule to JSON and deserializing it SHALL produce an equivalent rule object (round-trip property).
2. FOR ALL valid Incident payloads, invoking the Remediation_Engine twice with the same payload and the same Risk_Mode SHALL produce identical audit log outcomes for the second invocation (idempotency — cooldown suppresses the second execution).
3. THE Remediation_Engine SHALL produce a deterministic set of matched rules for any given Incident and rule configuration — the same input SHALL always produce the same matched rule set.
4. FOR ALL audit log entries, the `audit_id` field SHALL be a valid UUID v4 string.
5. WHEN the Remediation_Engine is invoked with a Dry_Run flag, THE resulting audit log entries SHALL have `dry_run` equal to `true` and `outcome` equal to `suppressed` for all actions that would have been executed.

