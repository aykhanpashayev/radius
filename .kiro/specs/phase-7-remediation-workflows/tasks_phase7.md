# Tasks — Phase 7: Remediation Workflows and Risk Modes

## Overview

Implementation tasks for Phase 7. All tasks are additive — no existing Lambda handlers, DynamoDB tables, API contracts, or Terraform modules are modified except where explicitly noted (Incident_Processor async invoke and API_Handler route table extension).

---

## Task List

- [x] 1. DynamoDB Tables and SNS Topic (Terraform)
  - [x] 1.1 Add `remediation_config` DynamoDB table to `infra/modules/dynamodb/main.tf` with PK `config_id`, KMS encryption, and PITR enabled
  - [x] 1.2 Add `remediation_audit_log` DynamoDB table to `infra/modules/dynamodb/main.tf` with PK `audit_id`, GSIs `IdentityTimeIndex` (PK: `identity_arn`, SK: `timestamp`, ALL) and `IncidentIndex` (PK: `incident_id`, SK: `timestamp`, KEYS_ONLY), TTL on `ttl`, KMS encryption, and PITR enabled
  - [x] 1.3 Add `remediation_topic` SNS topic to `infra/modules/sns/main.tf` with KMS encryption
  - [x] 1.4 Export new table names and topic ARN as Terraform outputs and wire them into `infra/main.tf`

- [x] 2. Remediation_Engine Lambda — Core Infrastructure (Terraform)
  - [x] 2.1 Add `remediation_engine` Lambda function resource to `infra/modules/lambda/main.tf` with `python3.12` runtime, `arm64` architecture, 60-second timeout, and environment variables: `REMEDIATION_CONFIG_TABLE`, `REMEDIATION_AUDIT_TABLE`, `REMEDIATION_TOPIC_ARN`, `DRY_RUN`
  - [x] 2.2 Create IAM role and policy for Remediation_Engine with least-privilege permissions: `iam:ListAccessKeys`, `iam:UpdateAccessKey`, `iam:DeleteLoginProfile`, `iam:ListAttachedUserPolicies`, `iam:ListAttachedRolePolicies`, `iam:ListUserPolicies`, `iam:ListRolePolicies`, `iam:GetUserPolicy`, `iam:GetRolePolicy`, `iam:DetachUserPolicy`, `iam:DetachRolePolicy`, `iam:DeleteUserPolicy`, `iam:DeleteRolePolicy`, `iam:GetRole`, `iam:UpdateAssumeRolePolicy`, `iam:PutUserPolicy`, `iam:PutRolePolicy`, `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query` on the two new tables, and `sns:Publish` on Remediation_Topic
  - [x] 2.3 Add `REMEDIATION_LAMBDA_ARN` as an optional environment variable on the existing `incident_processor` Lambda resource (empty string default)

- [x] 3. Remediation_Engine Lambda — Python Package Skeleton
  - [x] 3.1 Create `backend/functions/remediation_engine/` directory with `__init__.py` and `requirements.txt` (boto3 only, already available in Lambda runtime)
  - [x] 3.2 Create `backend/functions/remediation_engine/actions/__init__.py` with `ALL_ACTIONS` registry dict mapping action name strings to action class instances
  - [x] 3.3 Create `backend/functions/remediation_engine/actions/base.py` with `ActionOutcome` dataclass (`action_name`, `outcome`, `reason`, `details`) and abstract `RemediationAction` base class with `execute()` and `suppress()` methods

- [x] 4. Remediation Rule Engine — Config and Rule Matching
  - [x] 4.1 Create `backend/functions/remediation_engine/config.py` with `load_config()` (reads singleton `config_id=global` record from Remediation_Config table, returns safe defaults if absent) and `update_risk_mode()` (validates mode is one of `monitor`, `alert`, `enforce`, then updates the record)
  - [x] 4.2 Create `backend/functions/remediation_engine/engine.py` with `RemediationRuleEngine` class and `process(incident)` method implementing the full evaluation loop: load config → safety checks → match rules → collect actions → execute or suppress → notify → write summary audit record
  - [x] 4.3 Implement `match_rules(rules, incident)` function in `engine.py` that filters active rules by `min_severity` (using severity rank ordering Low=1 through Critical=5), `detection_types` (empty list matches all), and `identity_types` (empty list matches all)
  - [x] 4.4 Implement `deduplicate_actions(action_names)` in `engine.py` that returns a list of unique action names preserving first-occurrence order

- [x] 5. Safety Controls
  - [x] 5.1 Create `backend/functions/remediation_engine/safety.py` with `check_safety_controls(identity_arn, config, audit_table)` that checks in order: `excluded_arns` list → `protected_account_ids` list → 60-minute cooldown query → 24-hour rate limit (max 10 executions), returning a suppression reason string or `None`
  - [x] 5.2 Implement `_query_recent_executions(audit_table, identity_arn, hours)` in `safety.py` using `IdentityTimeIndex` GSI to count audit entries with `outcome=executed` within the given time window

- [x] 6. Audit Log
  - [x] 6.1 Create `backend/functions/remediation_engine/audit.py` with `write_audit_entry()` that writes a single action evaluation record (fields: `audit_id` UUID v4, `incident_id`, `identity_arn`, `rule_id`, `action_name`, `outcome`, `risk_mode`, `dry_run`, `timestamp`, `details` JSON string, `reason`, `ttl` 365 days from now)
  - [x] 6.2 Implement `write_audit_summary()` in `audit.py` that writes a summary record with `action_name=remediation_complete` and `details` containing counts of executed, skipped, failed, and suppressed actions
  - [x] 6.3 Implement `write_audit_suppressed()` and `write_audit_no_match()` convenience functions in `audit.py` for the safety-suppressed and no-rule-match paths

- [x] 7. Remediation Actions — Implementation
  - [x] 7.1 Create `backend/functions/remediation_engine/actions/disable_iam_user.py` implementing `DisableIAMUserAction`: skip non-IAMUser identities with `outcome=skipped/identity_type_not_supported`; deactivate all active access keys via `iam:UpdateAccessKey`; delete login profile via `iam:DeleteLoginProfile` (ignore `NoSuchEntityException`); return `outcome=executed` with `deactivated_key_ids` in details, or `outcome=failed` with error message on AWS API error
  - [x] 7.2 Create `backend/functions/remediation_engine/actions/remove_risky_policies.py` implementing `RemoveRiskyPoliciesAction`: list attached managed and inline policies; identify policies containing any of `iam:*`, `sts:AssumeRole`, `s3:*`, `ec2:*`, `lambda:*`, `organizations:*`; detach/delete each; return `outcome=skipped/no_risky_policies_found` if none found, `outcome=executed` with removed/failed lists otherwise; per-policy failures are non-fatal
  - [x] 7.3 Create `backend/functions/remediation_engine/actions/block_role_assumption.py` implementing `BlockRoleAssumptionAction`: skip non-role identities; fetch current trust policy; prepend a `Deny` statement with `Sid=RadiusBlockAssumption`; call `iam:UpdateAssumeRolePolicy`; store previous trust policy JSON in audit details for rollback; return `outcome=executed` or `outcome=failed`
  - [x] 7.4 Create `backend/functions/remediation_engine/actions/restrict_network_access.py` implementing `RestrictNetworkAccessAction`: build deny policy for `ec2:*`, `s3:*`, `vpc:*` with `NotIpAddress` condition using `allowed_ip_ranges` from config; attach as inline policy named `RadiusNetworkRestriction` via `iam:PutUserPolicy` or `iam:PutRolePolicy`; return `outcome=executed` with policy document in details, or `outcome=failed`
  - [x] 7.5 Create `backend/functions/remediation_engine/actions/notify_security_team.py` implementing `NotifySecurityTeamAction`: publish structured JSON to Remediation_Topic SNS including `incident_id`, `identity_arn`, `detection_type`, `severity`, `risk_mode`, `actions_taken`, `timestamp`, `dashboard_link`; skip publish when `risk_mode=monitor`; return `outcome=executed`, `outcome=suppressed`, or `outcome=failed`
  - [x] 7.6 Register all five action classes in `actions/__init__.py` `ALL_ACTIONS` dict

- [x] 8. Lambda Handler
  - [x] 8.1 Create `backend/functions/remediation_engine/handler.py` with `lambda_handler(event, context)` that reads env vars, constructs `RemediationRuleEngine`, calls `engine.process(event)`, and returns a status dict; handles `ValidationError` by returning `{"status": "skipped", "reason": ...}` without raising

- [x] 9. Incident_Processor Integration
  - [x] 9.1 Add `_invoke_remediation(incident, remediation_lambda_arn)` helper to `backend/functions/incident_processor/processor.py` that async-invokes the Remediation_Engine Lambda (`InvocationType="Event"`) and swallows all exceptions with a warning log
  - [x] 9.2 Call `_invoke_remediation()` from `create_incident()` in `processor.py` only when `incident["severity"]` is in `{"High", "Very High", "Critical"}` and `REMEDIATION_LAMBDA_ARN` env var is set and non-empty

- [x] 10. API Handler Extension
  - [x] 10.1 Add six new handler functions to `backend/functions/api_handler/handlers.py`: `get_remediation_config`, `put_remediation_mode`, `list_remediation_rules`, `create_remediation_rule`, `delete_remediation_rule`, `list_remediation_audit`
  - [x] 10.2 Register the six new routes in the `_ROUTES` list in `backend/functions/api_handler/handler.py`: `GET /remediation/config`, `PUT /remediation/config/mode`, `GET /remediation/rules`, `POST /remediation/rules`, `DELETE /remediation/rules/{rule_id}`, `GET /remediation/audit`
  - [x] 10.3 Add `REMEDIATION_CONFIG_TABLE` and `REMEDIATION_AUDIT_TABLE` environment variables to the `api_handler` Lambda resource in Terraform
  - [x] 10.4 Add IAM permissions for `api_handler` Lambda role: `dynamodb:GetItem`, `dynamodb:PutItem`, `dynamodb:UpdateItem`, `dynamodb:Query` on Remediation_Config and Remediation_Audit_Log tables

- [x] 11. Unit Tests
  - [x] 11.1 Create `backend/tests/test_remediation_config.py` testing `load_config()` default values when table is empty, `update_risk_mode()` accepts valid modes, and `update_risk_mode()` raises `ValidationError` for invalid modes
  - [x] 11.2 Create `backend/tests/test_remediation_engine.py` testing rule matching logic: `min_severity` threshold, `detection_types` filter (empty = match all), `identity_types` filter (empty = match all), multiple matched rules produce deduplicated action list, no-match path writes audit entry
  - [x] 11.3 Create `backend/tests/test_remediation_safety.py` testing each safety control in isolation: `excluded_arns` suppression, `protected_account_ids` suppression, cooldown suppression, rate limit suppression, and the pass-through case where no controls fire
  - [x] 11.4 Create `backend/tests/test_remediation_actions.py` with mocked `boto3` IAM client testing each action: `DisableIAMUserAction` skips non-user ARNs, deactivates keys, handles missing login profile; `RemoveRiskyPoliciesAction` skips when no risky policies found, removes matching policies, tolerates per-policy failures; `BlockRoleAssumptionAction` skips non-role ARNs, prepends deny statement, stores previous policy; `RestrictNetworkAccessAction` attaches correct inline policy; `NotifySecurityTeamAction` skips publish in monitor mode
  - [x] 11.5 Create `backend/tests/test_remediation_audit.py` testing `write_audit_entry()` produces records with valid UUID v4 `audit_id`, correct `ttl` (~365 days from now within 60-second tolerance), and all required fields present

- [x] 12. Property-Based Tests
  - [x] 12.1 Create `backend/tests/test_remediation_properties.py` with Hypothesis strategy `valid_remediation_rule_strategy()` generating rules with valid `min_severity`, `detection_types`, `identity_types`, and `actions` values
  - [x] 12.2 Write property test `test_rule_serialization_round_trip`: for any valid rule, `deserialize(serialize(rule)) == rule` (validates Requirement 12.1)
  - [x] 12.3 Write property test `test_severity_ordering_invariant`: for any two severity levels A > B, any incident matched by a rule with `min_severity=A` is also matched by a rule with `min_severity=B` (validates Requirement 2.4 / Design Property 6)
  - [x] 12.4 Write property test `test_audit_id_is_uuid4`: for any audit entry written by `write_audit_entry()`, the `audit_id` field matches the UUID v4 regex pattern (validates Requirement 12.4 / Design Property 4)
  - [x] 12.5 Write property test `test_monitor_mode_suppresses_all_actions`: for any Incident and any rule configuration, when `risk_mode=monitor`, all `ActionOutcome.outcome` values equal `suppressed` (validates Requirement 1.2 / Design Property 5)

- [ ] 13. Integration Tests
  - [ ] 13.1 Create `backend/tests/integration/test_remediation_integration.py` with moto fixtures for DynamoDB (Remediation_Config, Remediation_Audit_Log) and SNS (Remediation_Topic) and IAM
  - [ ] 13.2 Write integration test `test_monitor_mode_no_mutations`: invoke engine with a Critical incident and a matching rule in monitor mode; assert zero IAM API calls made and audit entries have `outcome=suppressed`
  - [ ] 13.3 Write integration test `test_alert_mode_notifies_no_mutations`: invoke engine in alert mode; assert SNS message published to Remediation_Topic and zero IAM mutations performed
  - [ ] 13.4 Write integration test `test_enforce_mode_executes_actions`: invoke engine in enforce mode with `disable_iam_user` rule; assert IAM access keys deactivated and audit entry has `outcome=executed`
  - [ ] 13.5 Write integration test `test_cooldown_suppresses_second_invocation`: invoke engine twice with same incident within 60 minutes; assert second invocation produces all `outcome=suppressed` with `reason=cooldown_active`
  - [ ] 13.6 Write integration test `test_excluded_arn_suppressed`: add identity ARN to `excluded_arns` config; invoke engine; assert `outcome=suppressed` with `reason=identity_excluded`
  - [ ] 13.7 Write integration test `test_dry_run_flag_overrides_enforce_mode`: set `risk_mode=enforce` in config but pass `dry_run=true` in payload; assert all outcomes are `suppressed` and audit entries have `dry_run=true`
  - [ ] 13.8 Write integration test `test_audit_log_completeness`: invoke engine with two matched rules each having two actions; assert total audit entries written equals 4 action entries plus 1 summary entry

- [ ] 14. Documentation
  - [ ] 14.1 Add a `Remediation Workflows` section to `docs/architecture.md` describing the new pipeline branch from Incident_Processor → Remediation_Engine, the three Risk Modes, and the two new DynamoDB tables
  - [ ] 14.2 Create `docs/remediation.md` documenting: the three Risk Modes and how to change them, all five remediation actions with trigger conditions and rollback procedures, the safety controls (cooldown, rate limit, exclusions), the audit log schema, and example API calls for configuring rules

