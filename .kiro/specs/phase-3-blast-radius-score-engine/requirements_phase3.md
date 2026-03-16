# Phase 3 Requirements: Blast Radius Score Engine

## Overview

Phase 3 implements the real scoring logic inside the existing Score_Engine Lambda function. The Blast Radius Score quantifies how much damage a compromised IAM identity could cause across an AWS Organization. Scores are rule-based, transparent, and explainable — each score record includes the contributing factors that produced it.

Phase 3 extends Phase 2 infrastructure without modifying existing DynamoDB tables, APIs, or Lambda function signatures.

---

## Requirement 1: Scoring Model Foundation

**1.1** The Score_Engine must calculate a Blast Radius Score in the range 0–100 (inclusive) for each active IAM identity.

**1.2** The score must be composed of weighted contributions from individual scoring rules. Each rule contributes a sub-score, and the final score is the sum of all rule contributions capped at 100.

**1.3** The scoring model must be rule-based and deterministic: given the same input data, the same score must always be produced.

**1.4** Each scoring rule must have a unique `rule_id`, a human-readable `rule_name`, a `weight` (0.0–1.0), and a `max_contribution` (integer, 0–100).

**1.5** The Score_Engine must implement the `ScoringRule` abstract interface already defined in `interfaces.py`. Each concrete rule must implement the `calculate(identity_arn, context)` method.

**1.6** The scoring context passed to each rule must include: the Identity_Profile record, recent Event_Summary records (last 90 days), Trust_Relationship records where the identity is the source, and open Incident records for the identity.

**1.7** Severity levels must follow the Phase 2 classification already implemented in `classify_severity()`:
- 0–19: Low
- 20–39: Moderate
- 40–59: High
- 60–79: Very High
- 80–100: Critical

**1.8** The `contributing_factors` field in the Blast_Radius_Score record must list each rule that contributed a non-zero score, in the format: `"<rule_name>: +<points>"` (e.g., `"AdminPrivileges: +25"`).

**1.9** The Score_Engine must preserve the previous score and calculate `score_change` (new score minus previous score) when a prior record exists in the Blast_Radius_Score table.

---

## Requirement 2: Scoring Rules

The following eight rules must be implemented. Each rule is evaluated independently and contributes points to the total score.

### Rule 1: Administrative Privileges (rule_id: `admin_privileges`)

**2.1** The rule must award points when the identity has demonstrated administrative-level behavior in CloudTrail events.

**2.2** Administrative behavior is defined as: performing IAM write operations (CreateUser, CreateRole, AttachUserPolicy, AttachRolePolicy, PutUserPolicy, PutRolePolicy, CreatePolicy, CreatePolicyVersion), or performing actions across 5 or more distinct AWS services within the scoring window.

**2.3** Max contribution: 25 points.

**2.4** Point allocation:
- IAM write operations detected: +20 points
- Actions across 5+ distinct services: +5 additional points

### Rule 2: IAM Permissions Scope (rule_id: `iam_permissions_scope`)

**2.5** The rule must award points based on the breadth of IAM-related actions the identity has performed.

**2.6** IAM-related actions are any CloudTrail events where `event_type` starts with `iam:` or the event name is in the IAM service namespace.

**2.7** Max contribution: 20 points.

**2.8** Point allocation:
- 1–4 distinct IAM actions observed: +5 points
- 5–9 distinct IAM actions observed: +10 points
- 10+ distinct IAM actions observed: +20 points

### Rule 3: Ability to Modify IAM (rule_id: `iam_modification`)

**2.9** The rule must award points when the identity has performed IAM mutation events that could grant or escalate permissions.

**2.10** IAM mutation events include: `AttachUserPolicy`, `AttachRolePolicy`, `AttachGroupPolicy`, `PutUserPolicy`, `PutRolePolicy`, `PutGroupPolicy`, `CreatePolicyVersion`, `SetDefaultPolicyVersion`, `AddUserToGroup`.

**2.11** Max contribution: 20 points.

**2.12** Point allocation:
- 1–2 IAM mutation events: +10 points
- 3+ IAM mutation events: +20 points

### Rule 4: Ability to Disable Logging (rule_id: `logging_disruption`)

**2.13** The rule must award points when the identity has performed events that could disable or tamper with audit logging.

**2.14** Logging disruption events include: `StopLogging`, `DeleteTrail`, `UpdateTrail`, `PutEventSelectors`, `DeleteFlowLogs`, `DeleteLogGroup`, `DeleteLogStream`.

**2.15** Max contribution: 20 points.

**2.16** Point allocation:
- Any logging disruption event detected: +20 points

### Rule 5: Cross-Account Trust Relationships (rule_id: `cross_account_trust`)

**2.17** The rule must award points based on the number of active cross-account trust relationships where the identity is the source (i.e., the identity can assume roles in other accounts).

**2.18** A cross-account trust relationship is a Trust_Relationship record with `relationship_type = "CrossAccount"` and `source_arn` matching the identity ARN.

**2.19** Max contribution: 15 points.

**2.20** Point allocation:
- 1 cross-account trust relationship: +5 points
- 2–3 cross-account trust relationships: +10 points
- 4+ cross-account trust relationships: +15 points

### Rule 6: Role Chaining Potential (rule_id: `role_chaining`)

**2.21** The rule must award points when the identity has performed AssumeRole events, indicating it can chain role assumptions to reach other identities.

**2.22** Role chaining is detected by counting AssumeRole, AssumeRoleWithSAML, and AssumeRoleWithWebIdentity events in the Event_Summary records.

**2.23** Max contribution: 10 points.

**2.24** Point allocation:
- 1–2 AssumeRole events: +5 points
- 3+ AssumeRole events: +10 points

### Rule 7: Privilege Escalation Capabilities (rule_id: `privilege_escalation`)

**2.25** The rule must award points when the identity has performed event sequences that indicate privilege escalation attempts or capabilities.

**2.26** Privilege escalation indicators include: creating a new IAM user followed by attaching a policy, creating a policy version with `setAsDefault=true`, adding a user to a group with admin policies, or performing `PassRole` events.

**2.27** Specific escalation events: `CreateUser` + `AttachUserPolicy` within the same scoring window, `CreatePolicyVersion` with `setAsDefault`, `AddUserToGroup`, `PassRole`.

**2.28** Max contribution: 15 points.

**2.29** Point allocation:
- 1 escalation indicator: +8 points
- 2+ escalation indicators: +15 points

### Rule 8: Lateral Movement Potential (rule_id: `lateral_movement`)

**2.30** The rule must award points when the identity has demonstrated behavior consistent with lateral movement across accounts or services.

**2.31** Lateral movement indicators include: AssumeRole events targeting roles in accounts different from the identity's home account, EC2 instance profile usage (`RunInstances` with IAM instance profile), and federation events (`GetFederationToken`, `AssumeRoleWithWebIdentity`).

**2.32** Max contribution: 10 points.

**2.33** Point allocation:
- Cross-account AssumeRole events: +5 points
- EC2 instance profile usage: +3 points
- Federation events: +2 points
- (Points are additive up to max contribution of 10)

---

## Requirement 3: Score Calculation Trigger

**3.1** The Score_Engine must be invocable in two modes:
- **Single-identity mode**: invoked with `{"identity_arn": "<arn>"}` to score one identity.
- **Batch mode**: invoked with an empty payload `{}` to score all active identities.

**3.2** In batch mode, the Score_Engine must scan the Identity_Profile table for all records where `is_active = true` and calculate a score for each.

**3.3** The Score_Engine must be invocable by the Event_Normalizer after processing a CloudTrail event, passing the `identity_arn` of the event source for single-identity rescoring.

**3.4** The Score_Engine must also support scheduled invocation (via EventBridge Scheduler or CloudWatch Events) for periodic batch rescoring of all identities.

**3.5** The Score_Engine must handle invocation errors gracefully: if scoring fails for one identity in batch mode, it must log the error and continue processing remaining identities.

**3.6** The Score_Engine must return a response indicating the number of scores calculated and any failures: `{"status": "ok", "records_written": N, "failures": M}`.

---

## Requirement 4: Data Retrieval for Scoring Context

**4.1** For each identity being scored, the Score_Engine must retrieve:
- The Identity_Profile record from the Identity_Profile table.
- Event_Summary records for the identity from the last 90 days, queried using the primary key (identity_arn).
- Trust_Relationship records where `source_arn` matches the identity ARN, queried using the primary key.
- Open Incident records for the identity, queried using the IdentityIndex GSI.

**4.2** Event retrieval must use pagination to handle identities with large event histories. The Score_Engine must retrieve all pages up to a maximum of 1,000 events per scoring run.

**4.3** If the Identity_Profile record does not exist for a given ARN, the Score_Engine must log a warning and skip scoring for that identity.

**4.4** All DynamoDB reads must use the existing `dynamodb_utils.py` helpers with retry logic.

---

## Requirement 5: Score Storage

**5.1** The calculated score must be written to the existing Blast_Radius_Score DynamoDB table using the existing `put_item` helper.

**5.2** The Blast_Radius_Score record must include: `identity_arn`, `score_value`, `severity_level`, `calculation_timestamp`, `contributing_factors`, `previous_score` (if available), `score_change` (if available).

**5.3** The `calculation_timestamp` must be an ISO 8601 UTC timestamp.

**5.4** Writing a new score must overwrite the existing record for the same `identity_arn` (the table stores the current snapshot only, consistent with Phase 2 design).

**5.5** If the DynamoDB write fails, the Score_Engine must log the error with the identity ARN and correlation ID, and count the failure in the response.

---

## Requirement 6: Score_Engine Integration with Event_Normalizer

**6.1** The Event_Normalizer must invoke the Score_Engine asynchronously after processing each CloudTrail event, passing the `identity_arn` of the event source.

**6.2** The Score_Engine invocation from Event_Normalizer must be fire-and-forget (InvocationType=Event). Failures must be logged but must not block event normalization.

**6.3** The existing Event_Normalizer invocation chain (Event_Normalizer → Detection_Engine, Event_Normalizer → Identity_Collector) must be preserved unchanged.

---

## Requirement 7: Scheduled Batch Scoring

**7.1** A scheduled EventBridge rule must invoke the Score_Engine in batch mode on a configurable schedule (default: every 6 hours).

**7.2** The schedule must be configurable per environment via Terraform variables (dev: every 24 hours, prod: every 6 hours).

**7.3** The scheduled invocation must pass an empty payload `{}` to trigger batch mode.

**7.4** The EventBridge schedule rule must be defined in the existing EventBridge Terraform module.

---

## Requirement 8: Observability

**8.1** The Score_Engine must emit structured JSON log entries for each scoring run, including: `identity_arn`, `score_value`, `severity_level`, `contributing_factors`, `correlation_id`, `duration_ms`.

**8.2** The Score_Engine must log a summary at the end of each batch run: total identities processed, total scores written, total failures, total duration.

**8.3** The Score_Engine must use the existing `logging_utils.py` correlation ID pattern.

**8.4** Score distribution metrics must be observable via CloudWatch Logs Insights queries against the structured log output.

---

## Requirement 9: Explainability

**9.1** Every Blast_Radius_Score record must include a `contributing_factors` list that explains which rules fired and how many points each contributed.

**9.2** The `contributing_factors` list must only include rules that contributed a non-zero score.

**9.3** The API endpoint `GET /scores/{arn}` (already implemented in Phase 2) must return the `contributing_factors` field as part of the score record, enabling clients to display score explanations.

**9.4** The scoring logic must be documented in `docs/scoring-model.md` with rule descriptions, weights, and example calculations.

---

## Requirement 10: Correctness Properties

The following properties must hold for all valid inputs and must be validated by property-based tests.

**10.1 Score bounds**: For any identity, the calculated score must satisfy `0 <= score <= 100`.

**10.2 Severity consistency**: The `severity_level` field must always equal `classify_severity(score_value)`.

**10.3 Contributing factors non-negativity**: Every entry in `contributing_factors` must represent a non-negative point contribution.

**10.4 Rule independence**: Disabling any single rule must not cause the score to increase.

**10.5 Determinism**: Scoring the same identity with the same context data must always produce the same score.

**10.6 Empty context baseline**: An identity with no events, no trust relationships, and no incidents must receive a score of 0.

**10.7 Score change consistency**: If `previous_score` and `score_change` are present, then `score_change == score_value - previous_score`.
