# Implementation Plan: Phase 3 Blast Radius Score Engine

## Overview

Phase 3 replaces the placeholder scoring logic in Score_Engine with a real, rule-based Blast Radius Score calculation. All work is additive — no Phase 2 infrastructure, tables, or APIs are modified.

**Implementation Language:** Python 3.11

**Key Deliverables:**
- `ScoringContext` data fetcher
- `RuleEngine` orchestrator
- 8 concrete scoring rules
- Updated `Score_Engine` handler (real logic, same interface)
- Event_Normalizer extended to invoke Score_Engine per event
- EventBridge scheduled rule for periodic batch rescoring
- IAM policy extensions for Score_Engine and Event_Normalizer
- Property-based and unit tests
- Scoring model documentation

**Important Constraints:**
- Do NOT modify DynamoDB table definitions
- Do NOT modify existing API endpoints
- Do NOT change the `lambda_handler` signature or return shape
- Preserve all Phase 2 Lambda invocation chains

**Priority Labels:**
- **must-have**: Required for Phase 3 functionality
- **should-have**: Important but not blocking
- **nice-to-have**: Optional enhancements

**Task Notation:**
- Tasks without `*` are required
- Tasks with `*` are optional (nice-to-have)

---

## Tasks

### Milestone 1: Scoring Foundation

- [x] 1. Extend ScoringRule interface and ScoreResult (must-have)
  - Add `max_contribution: int` class attribute to `ScoringRule` ABC in `interfaces.py`
  - Update `calculate()` signature: change `context: dict[str, Any]` to `context: "ScoringContext"`
  - Add forward reference import guard so `interfaces.py` does not import `context.py` (avoid circular import)
  - Verify `classify_severity()` and `ScoreResult` are unchanged
  - Remove `ScoreResult.placeholder()` classmethod (replaced by real logic)
  - **Deliverable:** Updated `interfaces.py` with extended `ScoringRule` contract
  - _Requirements: 1.4, 1.5_

- [x] 2. Implement ScoringContext (must-have)
  - Create `backend/functions/score_engine/context.py`
  - Define `ScoringContext` dataclass with fields: `identity_arn`, `identity_profile`, `events`, `trust_relationships`, `open_incidents`
  - Implement `ScoringContext.build(identity_arn, tables)` classmethod that fetches all data from DynamoDB
  - Fetch Identity_Profile using `get_item`
  - Fetch Event_Summary records using paginated query on primary key `identity_arn`, filter `timestamp >= 90 days ago`, max 1,000 items
  - Fetch Trust_Relationship records using primary key query `source_arn = identity_arn`
  - Fetch open Incident keys using IdentityIndex GSI, then `get_item` per `incident_id` for full records
  - Filter incidents client-side to `status in {"open", "investigating"}`
  - Use existing `dynamodb_utils.py` helpers for all reads
  - **Deliverable:** `ScoringContext` with `build()` factory that retrieves all scoring data
  - _Requirements: 1.6, 4.1, 4.2, 4.3, 4.4_

- [x] 3. Implement RuleEngine (must-have)
  - Create `backend/functions/score_engine/engine.py`
  - Define `RuleEngine` class with `rules: list[ScoringRule]` attribute
  - Implement `evaluate(context: ScoringContext) -> ScoreResult` method
  - For each rule: call `rule.calculate(identity_arn, context)`, clamp result to `[0, rule.max_contribution]`
  - Accumulate non-zero contributions into `contributing_factors` list as `"<rule_name>: +<points>"`
  - Sum all contributions and cap total at 100
  - Set `severity_level` using `classify_severity(total)`
  - Set `calculation_timestamp` to UTC ISO 8601
  - Return `ScoreResult` with all fields populated
  - **Deliverable:** `RuleEngine` that orchestrates all rules and produces a `ScoreResult`
  - _Requirements: 1.2, 1.3, 1.7, 1.8, 9.1, 9.2_

- [x] 4. Create rules package skeleton (must-have)
  - Create `backend/functions/score_engine/rules/` directory
  - Create `backend/functions/score_engine/rules/__init__.py` that exports all 8 rule classes
  - **Deliverable:** Rules package ready for rule implementations
  - _Requirements: 1.5_

- [x] 4a. Move extract_account_id to shared utils (should-have)
  - Create `backend/common/aws_utils.py`
  - Move `extract_account_id()` from `backend/functions/identity_collector/collector.py` into `aws_utils.py`
  - Update `identity_collector/collector.py` to import `extract_account_id` from `backend.common.aws_utils`
  - This avoids `lateral_movement.py` importing from a sibling Lambda function package
  - **Deliverable:** `backend/common/aws_utils.py` with `extract_account_id()`; `collector.py` updated to re-import from shared location
  - _Requirements: 1.5_

### Milestone 2: Scoring Rules Implementation

- [ ] 5. Implement AdminPrivileges rule (must-have)
  - Create `backend/functions/score_engine/rules/admin_privileges.py`
  - Define `AdminPrivilegesRule` with `rule_id = "admin_privileges"`, `rule_name = "AdminPrivileges"`, `max_contribution = 25`
  - Detect IAM write events: `{CreateUser, CreateRole, AttachUserPolicy, AttachRolePolicy, PutUserPolicy, PutRolePolicy, CreatePolicy, CreatePolicyVersion}`
  - Extract service from `event_type` by splitting on `:` (e.g., `iam:CreateUser` → `iam`)
  - Award +20 if any IAM write event found in context events
  - Award +5 additional if 5+ distinct services detected across all events
  - Return `min(points, 25)`
  - **Deliverable:** `AdminPrivilegesRule` implementation
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ] 6. Implement IAMPermissionsScope rule (must-have)
  - Create `backend/functions/score_engine/rules/iam_permissions_scope.py`
  - Define `IAMPermissionsScopeRule` with `rule_id = "iam_permissions_scope"`, `rule_name = "IAMPermissionsScope"`, `max_contribution = 20`
  - Filter events where `event_type` starts with `"iam:"`
  - Count distinct `event_type` values among filtered events
  - Return 0 / 5 / 10 / 20 based on count thresholds (0 / 1–4 / 5–9 / 10+)
  - **Deliverable:** `IAMPermissionsScopeRule` implementation
  - _Requirements: 2.5, 2.6, 2.7, 2.8_

- [ ] 7. Implement IAMModification rule (must-have)
  - Create `backend/functions/score_engine/rules/iam_modification.py`
  - Define `IAMModificationRule` with `rule_id = "iam_modification"`, `rule_name = "IAMModification"`, `max_contribution = 20`
  - Define mutation event set: `{AttachUserPolicy, AttachRolePolicy, AttachGroupPolicy, PutUserPolicy, PutRolePolicy, PutGroupPolicy, CreatePolicyVersion, SetDefaultPolicyVersion, AddUserToGroup}`
  - Extract event name from `event_type` by splitting on `:` and taking the last part
  - Count events whose name is in the mutation set
  - Return 0 / 10 / 20 based on count (0 / 1–2 / 3+)
  - **Deliverable:** `IAMModificationRule` implementation
  - _Requirements: 2.9, 2.10, 2.11, 2.12_

- [ ] 8. Implement LoggingDisruption rule (must-have)
  - Create `backend/functions/score_engine/rules/logging_disruption.py`
  - Define `LoggingDisruptionRule` with `rule_id = "logging_disruption"`, `rule_name = "LoggingDisruption"`, `max_contribution = 20`
  - Define disruption event set: `{StopLogging, DeleteTrail, UpdateTrail, PutEventSelectors, DeleteFlowLogs, DeleteLogGroup, DeleteLogStream}`
  - Return 20 if any event name is in the disruption set, else 0
  - **Deliverable:** `LoggingDisruptionRule` implementation
  - _Requirements: 2.13, 2.14, 2.15, 2.16_

- [ ] 9. Implement CrossAccountTrust rule (must-have)
  - Create `backend/functions/score_engine/rules/cross_account_trust.py`
  - Define `CrossAccountTrustRule` with `rule_id = "cross_account_trust"`, `rule_name = "CrossAccountTrust"`, `max_contribution = 15`
  - Filter `context.trust_relationships` where `relationship_type == "CrossAccount"`
  - Return 0 / 5 / 10 / 15 based on count (0 / 1 / 2–3 / 4+)
  - **Deliverable:** `CrossAccountTrustRule` implementation
  - _Requirements: 2.17, 2.18, 2.19, 2.20_

- [ ] 10. Implement RoleChaining rule (must-have)
  - Create `backend/functions/score_engine/rules/role_chaining.py`
  - Define `RoleChainingRule` with `rule_id = "role_chaining"`, `rule_name = "RoleChaining"`, `max_contribution = 10`
  - Count events where event name is in `{AssumeRole, AssumeRoleWithSAML, AssumeRoleWithWebIdentity}`
  - Return 0 / 5 / 10 based on count (0 / 1–2 / 3+)
  - **Deliverable:** `RoleChainingRule` implementation
  - _Requirements: 2.21, 2.22, 2.23, 2.24_

- [ ] 11. Implement PrivilegeEscalation rule (must-have)
  - Create `backend/functions/score_engine/rules/privilege_escalation.py`
  - Define `PrivilegeEscalationRule` with `rule_id = "privilege_escalation"`, `rule_name = "PrivilegeEscalation"`, `max_contribution = 15`
  - Collect all event names from context events into a set
  - Count indicators: (1) `CreateUser` AND `AttachUserPolicy` both present, (2) `CreatePolicyVersion` present, (3) `AddUserToGroup` present, (4) `PassRole` present
  - Return 0 / 8 / 15 based on indicator count (0 / 1 / 2+)
  - **Deliverable:** `PrivilegeEscalationRule` implementation
  - _Requirements: 2.25, 2.26, 2.27, 2.28, 2.29_

- [ ] 12. Implement LateralMovement rule (must-have)
  - Create `backend/functions/score_engine/rules/lateral_movement.py`
  - Define `LateralMovementRule` with `rule_id = "lateral_movement"`, `rule_name = "LateralMovement"`, `max_contribution = 10`
  - Extract identity account ID from `identity_arn` using `extract_account_id()` from `backend/common/aws_utils.py` (moved from `identity_collector/collector.py` — see Task 12a below)
  - Award +5 if any `AssumeRole` event targets a role in a different account (read `event_parameters.roleArn`, extract account; note: Event_Normalizer normalizes `requestParameters.roleArn` into `event_parameters.roleArn`)
  - Award +3 if any `RunInstances` event present
  - Award +2 if any `GetFederationToken` or `AssumeRoleWithWebIdentity` event present
  - Return `min(points, 10)`
  - **Deliverable:** `LateralMovementRule` implementation
  - _Requirements: 2.30, 2.31, 2.32, 2.33_

### Milestone 3: Score_Engine Handler and Integration

- [ ] 13. Rewrite Score_Engine handler with real scoring logic (must-have)
  - Update `backend/functions/score_engine/handler.py`
  - Import `RuleEngine` from `engine.py` and `ScoringContext` from `context.py`
  - Instantiate `RuleEngine` once outside `lambda_handler` (module-level, for Lambda warm reuse)
  - In `lambda_handler`: determine mode (single vs batch), iterate identities
  - For each identity: call `ScoringContext.build()`, skip if `identity_profile` is empty, call `engine.evaluate()`
  - Read existing score from Blast_Radius_Score table before writing (for `previous_score` and `score_change`)
  - Call `_write_score()` with the `ScoreResult`
  - Track `written` and `failures` counts separately
  - Return `{"status": "ok", "records_written": written, "failures": failures}` (remove `"placeholder": True`)
  - Preserve `_scan_active_identities()` helper unchanged
  - Preserve `_write_score()` helper unchanged
  - **Deliverable:** Score_Engine handler with real scoring logic, same external interface
  - _Requirements: 1.1, 1.9, 3.1, 3.2, 3.5, 3.6, 5.1, 5.2, 5.3, 5.4, 5.5, 8.1, 8.2, 8.3_

- [ ] 14. Extend Event_Normalizer to invoke Score_Engine (must-have)
  - Update `backend/functions/event_normalizer/handler.py`
  - Add async invocation of Score_Engine after existing Detection_Engine and Identity_Collector invocations
  - Pass `{"identity_arn": identity_arn}` as payload
  - Use `InvocationType="Event"` (fire-and-forget)
  - Read `SCORE_ENGINE_FUNCTION_NAME` from environment variables
  - Handle invocation errors: log and continue (do not raise)
  - Preserve existing invocations of Detection_Engine and Identity_Collector unchanged
  - **Deliverable:** Event_Normalizer invoking Score_Engine per processed event
  - _Requirements: 6.1, 6.2, 6.3_

### Milestone 4: Infrastructure Updates

- [ ] 15. Add Score_Engine IAM permissions (must-have)
  - Update `infra/modules/lambda/iam.tf`
  - Add `dynamodb:Query` and `dynamodb:GetItem` permissions on `Event_Summary` table ARN to Score_Engine IAM policy
  - Add `dynamodb:Query` and `dynamodb:GetItem` permissions on `Trust_Relationship` table ARN to Score_Engine IAM policy
  - Add `dynamodb:Query` and `dynamodb:GetItem` permissions on `Incident` table ARN and its GSI ARN to Score_Engine IAM policy
  - Verify existing `Identity_Profile` and `Blast_Radius_Score` permissions are already present
  - **Deliverable:** Score_Engine IAM role with read access to all required tables
  - _Requirements: 4.4_

- [ ] 16. Add Event_Normalizer permission to invoke Score_Engine (must-have)
  - Update `infra/modules/lambda/iam.tf`
  - Add `lambda:InvokeFunction` permission on Score_Engine function ARN to Event_Normalizer IAM policy
  - **Deliverable:** Event_Normalizer IAM role with permission to invoke Score_Engine
  - _Requirements: 6.1_

- [ ] 17. Add SCORE_ENGINE_FUNCTION_NAME environment variable to Event_Normalizer (must-have)
  - Update `infra/modules/lambda/main.tf`
  - Add `SCORE_ENGINE_FUNCTION_NAME = aws_lambda_function.score_engine.function_name` to Event_Normalizer environment block
  - **Deliverable:** Event_Normalizer Lambda configured with Score_Engine function name
  - _Requirements: 6.1_

- [ ] 18. Add EventBridge scheduled rule for batch scoring (must-have)
  - Update `infra/modules/eventbridge/main.tf`
  - Add `aws_cloudwatch_event_rule` resource with `schedule_expression = var.score_engine_schedule`
  - Add `aws_cloudwatch_event_target` pointing to Score_Engine Lambda ARN with empty JSON input `"{}"`
  - Add `aws_lambda_permission` granting EventBridge permission to invoke Score_Engine
  - Update `infra/modules/eventbridge/variables.tf` with `score_engine_schedule` (string) and `score_engine_function_arn` (string) variables
  - **Deliverable:** EventBridge scheduled rule invoking Score_Engine in batch mode
  - _Requirements: 7.1, 7.3, 7.4_

- [ ] 19. Configure schedule per environment (must-have)
  - Update `infra/envs/dev/terraform.tfvars`: add `score_engine_schedule = "rate(24 hours)"`
  - Update `infra/envs/prod/terraform.tfvars`: add `score_engine_schedule = "rate(6 hours)"`
  - Pass `score_engine_schedule` and `score_engine_function_arn` through environment `main.tf` to eventbridge module
  - **Deliverable:** Environment-specific batch scoring schedules
  - _Requirements: 7.2_

- [ ] 20. Run terraform validate (must-have)
  - Run `terraform init` and `terraform validate` in `infra/envs/dev/`
  - Resolve any variable reference or resource dependency errors
  - **Deliverable:** Validated Terraform configuration with no errors
  - _Requirements: 7.4_

### Milestone 5: Testing

- [ ] 21. Write unit tests for ScoringContext (must-have)
  - Create `backend/tests/test_scoring_context.py`
  - Mock DynamoDB responses using `unittest.mock.patch`
  - Test `build()` returns correct `ScoringContext` fields from mocked DynamoDB responses
  - Test that events are filtered to last 90 days
  - Test that pagination is handled (multiple pages of events)
  - Test that missing Identity_Profile returns empty dict
  - Test that incidents are filtered to `status in {"open", "investigating"}`
  - **Deliverable:** Unit tests for `ScoringContext.build()`
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 22. Write unit tests for each scoring rule (must-have)
  - Create `backend/tests/test_scoring_rules.py`
  - For each of the 8 rules, test:
    - Zero input → 0 points
    - Minimum threshold input → minimum non-zero points
    - Maximum threshold input → `max_contribution` points
    - Output never exceeds `max_contribution`
  - Use synthetic `ScoringContext` objects (no DynamoDB calls)
  - **Deliverable:** Unit tests covering all 8 scoring rules
  - _Requirements: 2.1–2.33_

- [ ] 23. Write unit tests for RuleEngine (must-have)
  - Create `backend/tests/test_rule_engine.py`
  - Test that total score is capped at 100 when rule contributions sum > 100
  - Test that `contributing_factors` only includes rules with non-zero contributions
  - Test that `contributing_factors` format is `"<rule_name>: +<points>"`
  - Test that `severity_level` matches `classify_severity(score_value)`
  - Test empty context produces score of 0
  - **Deliverable:** Unit tests for `RuleEngine.evaluate()`
  - _Requirements: 1.2, 1.3, 1.7, 1.8, 9.1, 9.2_

- [ ] 24. Write property-based tests for scoring correctness (must-have)
  - Create `backend/tests/test_score_engine_properties.py`
  - Install `hypothesis` in `backend/functions/score_engine/requirements.txt` (test dependency only)
  - Implement Hypothesis strategies: `event_summary_strategy`, `trust_relationship_strategy`, `scoring_context_strategy`
  - **Property 1 — Score bounds**: for any generated context, `0 <= score <= 100`
  - **Property 2 — Severity consistency**: `severity_level == classify_severity(score_value)`
  - **Property 3 — Contributing factors non-negativity**: all factor point values >= 0
  - **Property 4 — Rule independence**: zeroing any single rule's inputs does not increase the total score
  - **Property 5 — Determinism**: scoring the same context twice produces identical `ScoreResult`
  - **Property 6 — Empty context baseline**: context with no events, no trust relationships, no incidents → score == 0
  - **Property 7 — Score change consistency**: if `previous_score` set, `score_change == score_value - previous_score`
  - **Deliverable:** Property-based test suite validating all 7 correctness properties
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6, 10.7_

### Milestone 6: Documentation

- [ ] 25. Write scoring model documentation (must-have)
  - Create `docs/scoring-model.md`
  - Document the scoring model overview: rule-based, deterministic, 0–100 range
  - Document each of the 8 rules: rule_id, rule_name, max_contribution, trigger conditions, point allocation
  - Include a worked example: sample identity with 3 rules firing, showing contributing_factors and final score
  - Document severity level thresholds (Low / Moderate / High / Very High / Critical)
  - Document the `contributing_factors` field format
  - Document the two invocation modes (single-identity and batch)
  - Document the batch schedule (dev: 24h, prod: 6h)
  - **Deliverable:** `docs/scoring-model.md` with complete scoring model reference
  - _Requirements: 9.4_

- [ ] 26. Update Phase 2 scope documentation (should-have)
  - Update `docs/phase-2-scope.md` to note that Score_Engine placeholder has been replaced in Phase 3
  - Add a brief Phase 3 summary section referencing `docs/scoring-model.md`
  - **Deliverable:** Updated scope documentation reflecting Phase 3 completion
  - _Requirements: 9.4_

- [ ]* 27. Write integration tests for end-to-end scoring pipeline (nice-to-have)
  - Create `backend/tests/test_score_engine_integration.py`
  - Test full pipeline: inject synthetic Event_Summary + Trust_Relationship records into DynamoDB (localstack or moto), invoke Score_Engine, verify Blast_Radius_Score record written with correct fields
  - Test single-identity mode and batch mode
  - Test that `previous_score` and `score_change` are populated on second invocation
  - **Deliverable:** Integration tests for Score_Engine against mocked DynamoDB
  - _Requirements: 3.1, 3.2, 5.1, 5.2, 5.4_

- [ ]* 28. Add CloudWatch Logs Insights query examples (nice-to-have)
  - Update `docs/monitoring.md` with example Logs Insights queries for Score_Engine
  - Query: score distribution by severity level
  - Query: identities whose score increased by more than 20 points in last 24 hours
  - Query: top 10 identities by score value
  - Query: batch run summary (records_written, failures per run)
  - **Deliverable:** Score_Engine monitoring query examples in `docs/monitoring.md`
  - _Requirements: 8.4_

---

## Notes

**Priority Labels:**
- **must-have**: 26 tasks (all milestones 1–6 required tasks)
- **should-have**: 1 task (Task 26 — scope doc update)
- **nice-to-have**: 2 tasks (Tasks 27–28 — integration tests, monitoring queries)

**Task Organization:**
- Milestone 1: Scoring Foundation (4 tasks — interfaces, context, engine, rules package)
- Milestone 2: Scoring Rules (8 tasks — one per rule)
- Milestone 3: Handler and Integration (2 tasks — handler rewrite, Event_Normalizer extension)
- Milestone 4: Infrastructure Updates (6 tasks — IAM, env vars, EventBridge schedule, validate)
- Milestone 5: Testing (4 tasks — context tests, rule tests, engine tests, property tests)
- Milestone 6: Documentation (4 tasks — scoring model, scope update, optional integration tests, optional monitoring)

**Key Architecture Decisions:**
- `RuleEngine` is instantiated at module level in `handler.py` for Lambda warm-start reuse
- Rules are stateless and read-only against `ScoringContext` — no DynamoDB calls inside rules
- `ScoringContext.build()` is the single point of data fetching, making rules fully testable without mocking DynamoDB
- `extract_account_id()` is imported from `identity_collector/collector.py` to avoid duplication
- No new DynamoDB tables or GSIs are added in Phase 3
- The `Blast_Radius_Score` table stores the current snapshot only (overwrite on each calculation)
- `contributing_factors` is a list of strings, not a nested object, to keep the DynamoDB schema flat

**Correctness Properties (from Requirement 10):**
All 7 properties are validated by property-based tests in Task 24. These tests must pass before Phase 3 is considered complete.
