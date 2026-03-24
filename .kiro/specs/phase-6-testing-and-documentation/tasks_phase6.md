# Implementation Plan: Phase 6 — Testing and Documentation

## Overview

Phase 6 brings Radius to production quality through two parallel workstreams: a comprehensive integration test suite and a complete documentation refresh. All work is purely additive — no Lambda handlers, DynamoDB table definitions, API contracts, or Terraform module interfaces are modified.

**Implementation Language:** Python (pytest + Hypothesis + moto)

**Key Deliverables:**
- `backend/tests/integration/conftest.py` — shared moto fixtures for all 5 DynamoDB tables + SNS
- `backend/tests/integration/test_pipeline_e2e.py` — normalizer → DynamoDB write verification + properties P1–P4
- `backend/tests/integration/test_detection_integration.py` — detection rule accuracy + property P5
- `backend/tests/integration/test_scoring_integration.py` — score correctness + DynamoDB write + property P6
- `backend/tests/integration/test_attack_scenarios.py` — all 5 attack scenarios + deduplication
- `backend/tests/integration/test_incident_processor.py` — incident lifecycle + SNS routing + properties P7–P9
- `docs/architecture.md` — updated with full pipeline diagram, all 5 tables, all 6 Lambdas, Terraform modules
- `docs/deployment.md` — updated with prerequisites, step-by-step setup, troubleshooting
- `docs/scoring-model.md` — verified all 8 rules, worked example, invocation modes
- `docs/detection-rules.md` — verified all 7 rules, deduplication, DetectionContext sources
- `docs/dashboard.md` — new: all pages, filtering, incident transitions, score display, dev setup, deployment
- `docs/developer-guide.md` — new: adding rules, test structure, running tests, injecting events, Lambda packaging

**Important Constraints:**
- Do NOT modify any existing Lambda handlers, DynamoDB table definitions, API contracts, or Terraform modules
- Integration tests call production business logic functions directly — no subprocess or HTTP invocations
- All moto mocking is applied at the fixture level via `autouse=True` — no per-test `@mock_aws` decorators
- The `IdentityIndex` GSI on the Incident table must use `KEYS_ONLY` projection to match `processor.py`'s `find_duplicate()` query
- Property-based tests use Hypothesis with `max_examples=100` minimum
- Each property test must include a comment tag: `# Feature: phase-6-testing-and-documentation, Property N: <text>`

---

## Tasks

### Milestone 1: Integration Test Infrastructure

- [x] 1. Create integration test directory and shared fixtures
  - Create `backend/tests/integration/__init__.py` (empty)
  - Create `backend/tests/integration/conftest.py` with:
    - `aws_credentials(monkeypatch)` fixture — `autouse=True`, sets `AWS_ACCESS_KEY_ID=testing`, `AWS_SECRET_ACCESS_KEY=testing`, `AWS_DEFAULT_REGION=us-east-1`
    - `dynamodb_tables(aws_credentials)` fixture — opens `mock_aws()` context, creates all 5 tables with exact PK/SK/GSI definitions matching `infra/modules/dynamodb/main.tf`, yields `dict` of table names, tears down on exit
    - `sns_topic(dynamodb_tables)` fixture — creates mocked SNS topic named `test-alert-topic`, yields its ARN
    - `table_names()` helper returning the standard name dict used across all test modules
  - Table definitions to replicate exactly:
    - `Identity_Profile`: PK=`identity_arn`; GSIs: `IdentityTypeIndex` (PK=`identity_type`), `AccountIndex` (PK=`account_id`)
    - `Blast_Radius_Score`: PK=`identity_arn`; GSIs: `ScoreRangeIndex` (PK=`severity_level`), `SeverityIndex` (PK=`severity_level`, SK=`score_value`)
    - `Incident`: PK=`incident_id`; GSIs: `StatusIndex` (PK=`status`), `SeverityIndex` (PK=`severity`), `IdentityIndex` (PK=`identity_arn`, SK=`creation_timestamp`, projection=`KEYS_ONLY`)
    - `Event_Summary`: PK=`identity_arn`, SK=`timestamp`; GSIs: `EventIdIndex` (PK=`event_id`), `EventTypeIndex` (PK=`event_type`), `TimeRangeIndex` (PK=`date_partition`, SK=`timestamp`)
    - `Trust_Relationship`: PK=`source_arn`, SK=`target_arn`; GSIs: `RelationshipTypeIndex` (PK=`relationship_type`), `TargetAccountIndex` (PK=`target_account_id`)
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

### Milestone 2: End-to-End Pipeline Tests

- [x] 2. Implement pipeline helper functions and example-based pipeline tests
  - Create `backend/tests/integration/test_pipeline_e2e.py`
  - Implement module-level pipeline helper functions (not test functions):
    - `_make_cloudtrail_event(event_name, identity_arn, account_id, event_time=None, extra_params=None)` — builds minimal valid CloudTrail event dict with `detail` wrapper
    - `_run_normalizer(raw_event)` — calls `parse_cloudtrail_event(raw_event)`, returns `event_summary`
    - `_run_collector(event_summary, raw_event, tables)` — calls `upsert_identity_profile()` and conditionally `record_trust_relationship()` for AssumeRole events
    - `_run_detection(event_summary, tables)` — builds `DetectionContext`, calls detection `RuleEngine().evaluate()`
    - `_run_score_engine(identity_arn, tables)` — builds `ScoringContext`, calls score `RuleEngine().evaluate()`, writes result to `Blast_Radius_Score` table
    - `_run_incident_processor(finding, tables, sns_topic_arn)` — calls `validate_finding`, `find_duplicate`, `create_incident` or `append_event_to_incident`, `publish_alert`
  - Write example-based tests:
    - `test_event_summary_written_to_dynamodb` — pass a `CreateUser` event through normalizer + `put_item`, assert record exists in `Event_Summary` table with correct `identity_arn`, `event_type`, `date_partition`
    - `test_identity_profile_created_on_first_event` — pass a `CreateUser` event through `_run_collector`, assert `Identity_Profile` record exists with `identity_arn`, `identity_type`, `account_id`, `last_activity_timestamp`
    - `test_trust_relationship_written_on_assume_role` — pass an `AssumeRole` event with `roleArn` in `requestParameters`, assert `Trust_Relationship` record exists with `source_arn`, `target_arn`, `relationship_type`, `source_account_id`, `target_account_id`
    - `test_invalid_event_raises_validation_error` — pass event missing `eventName`, assert `ValidationError` raised and zero DynamoDB writes
    - `test_missing_user_identity_raises_error` — pass event missing `userIdentity`, assert error raised
    - `test_missing_event_time_raises_error` — pass event missing `eventTime`, assert error raised
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 7.1, 7.2, 7.3_

- [x]* 3. Write property tests P1–P4 for pipeline round-trips
  - Add to `test_pipeline_e2e.py`:
  - `test_event_summary_write_round_trip` — Property 1: for any valid CloudTrail event generated by `valid_cloudtrail_event_strategy()`, assert Event_Summary record contains all required fields and `ttl` is within 60s of `now + 90 days`
    - `# Feature: phase-6-testing-and-documentation, Property 1: Event_Summary write round-trip`
    - **Validates: Requirements 2.1, 7.1, 7.6**
  - `test_identity_profile_upsert_round_trip` — Property 2: for any valid CloudTrail event, assert Identity_Profile record contains `identity_arn`, `identity_type`, `account_id`, `last_activity_timestamp`
    - `# Feature: phase-6-testing-and-documentation, Property 2: Identity_Profile upsert round-trip`
    - **Validates: Requirements 2.2, 7.2**
  - `test_trust_relationship_write_round_trip` — Property 3: for any AssumeRole-family event with valid `roleArn`, assert Trust_Relationship record contains all 5 required fields
    - `# Feature: phase-6-testing-and-documentation, Property 3: Trust_Relationship write round-trip`
    - **Validates: Requirements 2.3, 7.3**
  - `test_invalid_event_rejected` — Property 4: for any event missing one of `eventName`, `userIdentity`, `eventTime`, assert normalizer raises an error and zero DynamoDB writes occur
    - `# Feature: phase-6-testing-and-documentation, Property 4: Invalid event rejection`
    - **Validates: Requirements 2.6**
  - Implement `valid_cloudtrail_event_strategy()` and `assume_role_event_strategy()` Hypothesis strategies in this file
  - _Requirements: 2.1, 2.2, 2.3, 2.6, 7.1, 7.2, 7.3, 7.6_

- [x] 4. Checkpoint — Ensure pipeline tests pass
  - Ensure all tests pass, ask the user if questions arise.

### Milestone 3: Detection Rule Integration Tests

- [ ] 5. Write detection rule accuracy tests
  - Create `backend/tests/integration/test_detection_integration.py`
  - Load sample events from `sample-data/cloud-trail-events/` using a `_load_sample(filename)` helper
  - Write example-based tests:
    - `test_privilege_escalation_fires_on_sample_event` — load `suspicious-privilege-escalation.json`, run through `_run_detection`, assert at least one Finding with `detection_type == "privilege_escalation"`
    - `test_cross_account_role_assumption_fires_on_sample_event` — load `suspicious-cross-account-access.json`, assert Finding with `detection_type == "cross_account_role_assumption"`
    - `test_logging_disruption_fires_with_critical_severity` — construct `cloudtrail:StopLogging` event, assert Finding with `detection_type == "logging_disruption"` and `severity == "Critical"`
    - `test_root_user_activity_fires_with_very_high_severity` — construct event with `identity_type == "Root"` ARN (`arn:aws:iam::111111111111:root`), assert Finding with `detection_type == "root_user_activity"` and `severity == "Very High"`
    - `test_benign_list_users_produces_no_findings` — construct `iam:ListUsers` event with no suspicious context, assert empty findings list
    - `test_finding_detection_type_matches_rule_id` — for each of the 5 triggering events above, assert `finding.detection_type == rule.rule_id` for the matched finding
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

- [ ]* 6. Write property test P5 for detection finding validity
  - Add to `test_detection_integration.py`:
  - `test_detection_finding_validity` — Property 5: for any `(event_summary, DetectionContext)` pair that produces a Finding, assert `finding.detection_type` equals the rule's `rule_id` and `finding.confidence` is an integer in `[0, 100]`
    - `# Feature: phase-6-testing-and-documentation, Property 5: Detection finding validity`
    - **Validates: Requirements 3.6, 3.7**
  - Implement `triggering_event_strategy()` Hypothesis strategy that generates events known to trigger at least one rule
  - _Requirements: 3.6, 3.7_

### Milestone 4: Scoring Integration Tests

- [ ] 7. Write scoring correctness and DynamoDB write tests
  - Create `backend/tests/integration/test_scoring_integration.py`
  - Write example-based tests:
    - `test_iam_write_events_produce_nonzero_score` — build `ScoringContext` with `AttachUserPolicy` events, call `_run_score_engine`, assert `score_value > 0` and `severity_level != "Low"`
    - `test_empty_context_produces_zero_score` — build empty `ScoringContext`, assert `score_value == 0` and `severity_level == "Low"`
    - `test_logging_disruption_event_adds_contributing_factor` — build context with `cloudtrail:StopLogging` event, assert `"LoggingDisruption: +20"` in `contributing_factors`
    - `test_cross_account_trust_adds_contributing_factor` — build context with `CrossAccount` trust relationship, assert `"CrossAccountTrust"` appears in at least one contributing factor string
    - `test_score_written_to_dynamodb` — call `_run_score_engine`, assert `Blast_Radius_Score` record exists in DynamoDB with correct `identity_arn`, `score_value`, `severity_level`
    - `test_blast_radius_score_record_fields` — assert written record contains `identity_arn`, `score_value`, `severity_level`, `calculation_timestamp`, `contributing_factors`
    - `test_score_value_in_valid_range` — assert `0 <= score_value <= 100` for a variety of contexts
    - `test_severity_level_consistent_with_score` — assert `severity_level` matches documented thresholds for the written `score_value`
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 7.4_

- [ ]* 8. Write property test P6 for score write round-trip
  - Add to `test_scoring_integration.py`:
  - `test_score_write_round_trip` — Property 6: for any valid `ScoringContext`, assert written `Blast_Radius_Score` record has `score_value` in `[0, 100]` and `severity_level` is the correct classification per documented thresholds
    - `# Feature: phase-6-testing-and-documentation, Property 6: Score write round-trip`
    - **Validates: Requirements 4.5, 4.6, 4.7, 7.4**
  - Implement `scoring_context_strategy()` Hypothesis strategy (can reuse/adapt from `test_score_engine_properties.py`)
  - _Requirements: 4.5, 4.6, 4.7, 7.4_

- [ ] 9. Checkpoint — Ensure detection and scoring tests pass
  - Ensure all tests pass, ask the user if questions arise.

### Milestone 5: Attack Scenario Tests

- [ ] 10. Write attack scenario simulation tests
  - Create `backend/tests/integration/test_attack_scenarios.py`
  - Import `_make_cloudtrail_event` and pipeline helpers from `test_pipeline_e2e.py` (or extract to a shared `helpers.py` module in `integration/`)
  - Write one test per scenario:
    - `test_privilege_escalation_scenario` — inject `iam:CreateUser` at T+0, then `iam:AttachUserPolicy` at T+5m for same identity; run both through full pipeline; assert `Incident` record exists with `detection_type == "privilege_escalation"`
    - `test_cross_account_lateral_movement_scenario` — inject `sts:AssumeRole` with `roleArn` in account `987654321098`; assert `Incident` with `detection_type == "cross_account_role_assumption"`
    - `test_logging_disruption_scenario` — inject `cloudtrail:StopLogging`; assert `Incident` with `severity == "Critical"`
    - `test_api_burst_scenario` — inject 20x `ec2:DescribeInstances` events within 5 minutes for same identity (use `datetime.now(timezone.utc)` timestamps); assert `Incident` with `detection_type == "api_burst_anomaly"`
    - `test_root_user_activity_scenario` — inject event with `identity_arn = "arn:aws:iam::111111111111:root"` and `identity_type = "Root"`; assert `Incident` with `detection_type == "root_user_activity"`
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [ ] 11. Write deduplication scenario test
  - Add to `test_attack_scenarios.py`:
  - `test_deduplication_prevents_duplicate_incident` — inject `cloudtrail:StopLogging` twice for the same identity within 24 hours; run both through full pipeline including `_run_incident_processor`; scan `Incident` table and assert exactly 1 record exists for that `identity_arn` + `detection_type` pair; assert the existing record's `related_event_ids` contains both event IDs
  - _Requirements: 5.6, 6.4_

### Milestone 6: Incident Processor Integration Tests

- [ ] 12. Write incident lifecycle and SNS routing tests
  - Create `backend/tests/integration/test_incident_processor.py`
  - Set up SQS queue subscribed to the mocked SNS topic for SNS message assertion (moto pattern)
  - Write example-based tests:
    - `test_incident_created_with_all_required_fields` — call `create_incident` with valid finding dict; get item from DynamoDB; assert all 11 required fields present: `incident_id`, `identity_arn`, `detection_type`, `severity`, `confidence`, `status`, `creation_timestamp`, `update_timestamp`, `related_event_ids`, `status_history`, `notes`
    - `test_initial_status_is_open` — assert `status == "open"` on newly created incident
    - `test_initial_status_history_has_one_entry` — assert `len(status_history) == 1` and `status_history[0]["status"] == "open"`
    - `test_incident_id_is_valid_uuid4` — assert `incident_id` matches UUID v4 regex `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`
    - `test_duplicate_finding_appends_to_existing_incident` — create incident, then call `find_duplicate` + `append_event_to_incident` with same `identity_arn` + `detection_type`; assert still only 1 incident record; assert `related_event_ids` updated
    - `test_high_severity_publishes_sns_alert` — call `publish_alert` with `severity == "High"` incident; assert SNS message received on subscribed SQS queue
    - `test_very_high_severity_publishes_sns_alert` — same for `severity == "Very High"`
    - `test_critical_severity_publishes_sns_alert` — same for `severity == "Critical"`
    - `test_low_severity_does_not_publish_sns_alert` — call `publish_alert` with `severity == "Low"`; assert zero SNS messages
    - `test_moderate_severity_does_not_publish_sns_alert` — same for `severity == "Moderate"`
    - `test_status_transition_open_to_investigating` — call `transition_status` from `open` to `investigating`; assert `status == "investigating"`, `len(status_history) == 2`, `update_timestamp` updated
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 7.5_

- [ ]* 13. Write property tests P7–P9 for incident processor invariants
  - Add to `test_incident_processor.py`:
  - `test_incident_structure_invariant` — Property 7: for any valid Finding generated by `valid_finding_strategy()`, assert created Incident record contains all required fields, `incident_id` matches UUID v4 format, `status == "open"`, `len(status_history) == 1`
    - `# Feature: phase-6-testing-and-documentation, Property 7: Incident structure invariant`
    - **Validates: Requirements 6.1, 6.2, 6.3, 7.5**
  - `test_deduplication_invariant` — Property 8: for any `(identity_arn, detection_type)` pair, two Findings with the same pair within 24 hours produce exactly 1 Incident record in DynamoDB
    - `# Feature: phase-6-testing-and-documentation, Property 8: Deduplication invariant`
    - **Validates: Requirements 5.6, 6.4**
  - `test_sns_alert_routing` — Property 9: for any Finding, `publish_alert` publishes to SNS if and only if `severity` is one of `High`, `Very High`, `Critical`; Findings with `Low` or `Moderate` severity produce zero SNS publish calls
    - `# Feature: phase-6-testing-and-documentation, Property 9: SNS alert routing`
    - **Validates: Requirements 6.5, 6.6**
  - Implement `valid_finding_strategy()` Hypothesis strategy as specified in the design document
  - _Requirements: 5.6, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 7.5_

- [ ] 14. Final integration test checkpoint
  - Ensure all tests pass with `pytest backend/tests/integration/ -v`, ask the user if questions arise.

### Milestone 7: Architecture Documentation

- [ ] 15. Update docs/architecture.md
  - Rewrite `docs/architecture.md` to include:
    - Full text-based pipeline diagram showing: CloudTrail → EventBridge → Event_Normalizer → (Detection_Engine → Incident_Processor, Identity_Collector, Score_Engine) → API_Handler → Dashboard
    - All 5 DynamoDB tables with PK, SK, and purpose: `Identity_Profile`, `Blast_Radius_Score`, `Incident`, `Event_Summary`, `Trust_Relationship`
    - All 6 Lambda functions with trigger, purpose, and downstream invocations: `Event_Normalizer`, `Detection_Engine`, `Score_Engine`, `Incident_Processor`, `Identity_Collector`, `API_Handler`
    - Terraform module structure and dependencies: `dynamodb`, `lambda`, `eventbridge`, `apigateway`, `sns`, `cloudwatch`, `kms`
    - Design principles section: serverless, event-driven, cost-aware, explainable, multi-account
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

### Milestone 8: Deployment Documentation

- [ ] 16. Update docs/deployment.md
  - Update `docs/deployment.md` to include:
    - Prerequisites section: AWS CLI version, Terraform version, Python version (3.11+), required IAM permissions
    - Step-by-step first-time setup: S3 state bucket creation, backend configuration in `infra/envs/dev/main.tf`, variable configuration in `terraform.tfvars`
    - `build-lambdas.sh` usage with all supported flags
    - `deploy-infra.sh` usage including plan-only mode and auto-approve mode
    - `verify-deployment.sh` description and what it checks
    - Dev vs prod environment differences (table names, Lambda memory, log retention, alarm thresholds)
    - Rollback procedure using Terraform state versioning in S3
    - At least 3 troubleshooting scenarios with resolution steps (e.g. Lambda timeout, DynamoDB throttling, EventBridge rule not triggering)
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7, 9.8_

### Milestone 9: Scoring and Detection Rule Documentation

- [ ] 17. Verify and update docs/scoring-model.md
  - Review `backend/functions/score_engine/rules/` to confirm all 8 rules are documented
  - Verify `docs/scoring-model.md` documents each rule with: `rule_id`, `max_contribution`, trigger conditions, point values
  - Verify the 5 severity thresholds are documented: 0–19 Low, 20–39 Moderate, 40–59 High, 60–79 Very High, 80–100 Critical
  - Add or update the worked example to match current rule implementations (use a realistic identity with 3–4 contributing factors)
  - Verify `contributing_factors` field format is documented: `"<rule_name>: +<points>"`
  - Verify both invocation modes are documented: single-identity (EventBridge trigger) and batch (direct Lambda invoke)
  - Verify ScoringContext data sources are documented: Identity_Profile, Event_Summary (last 90 days, max 1,000 events), Trust_Relationship, Incident
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [ ] 18. Verify and update docs/detection-rules.md
  - Review `backend/functions/detection_engine/rules/` to confirm all 7 rules are documented
  - Verify `docs/detection-rules.md` documents each rule with: `rule_id`, `rule_name`, severity, confidence, rule type (single-event or context-aware), trigger conditions
  - Verify each rule has an example triggering event or context
  - Verify deduplication behavior is documented: 24-hour window keyed on `identity_arn` + `detection_type`
  - Verify DetectionContext data sources are documented: `recent_events_60m` and `prior_services_30d`
  - Verify summary table lists all 7 rules with severity and confidence values
  - Verify the 5 severity levels and their operational meaning are documented
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6_

### Milestone 10: New Documentation Files

- [ ] 19. Create docs/dashboard.md
  - Create `docs/dashboard.md` documenting:
    - All 5 dashboard pages: Identity List (`/`), Identity Detail (`/identities/:arn`), Incident List (`/incidents`), Incident Detail, Score Overview
    - How to filter identities by severity level and account ID using the UI controls
    - How to update incident status from the UI: open → investigating → resolved or false_positive; which statuses are terminal
    - Blast Radius Score display: severity colour coding (Critical=red, Very High=orange, High=amber, Moderate=yellow, Low=green), contributing factors breakdown
    - Local development setup: `npm install`, `npm run dev`, `VITE_API_BASE_URL` environment variable
    - Production build and S3 deployment: `npm run build`, `aws s3 sync`, CloudFront cache invalidation command
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_

- [ ] 20. Create docs/developer-guide.md
  - Create `docs/developer-guide.md` documenting:
    - Steps to add a new detection rule: create file in `backend/functions/detection_engine/rules/`, implement `DetectionRule` or `ContextAwareDetectionRule` interface, register in `rules/__init__.py`, add unit tests in `backend/tests/`
    - Steps to add a new scoring rule: create file in `backend/functions/score_engine/rules/`, implement `ScoringRule` interface, register in `rules/__init__.py`, add unit tests
    - Test structure: `backend/tests/` contains unit tests and property-based tests; `backend/tests/integration/` contains integration tests; how to run each subset
    - How to run the full test suite: `pytest backend/tests/ -v`; integration only: `pytest backend/tests/integration/ -v`; with coverage: `pytest backend/tests/ --cov=backend/functions`
    - How to inject sample events using `scripts/inject-events.py` for manual pipeline testing
    - Lambda packaging and deployment workflow: `build-lambdas.sh` then `deploy-infra.sh`
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

- [ ] 21. Final checkpoint — Ensure all tests pass and docs are complete
  - Ensure all tests pass with `pytest backend/tests/ -v`, ask the user if questions arise.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at each milestone boundary
- Property tests (P1–P9) validate universal correctness properties; unit tests validate specific examples and edge cases
- The `IdentityIndex` GSI on the Incident table must use `KEYS_ONLY` projection — this is critical for `find_duplicate()` to work correctly under moto
- API burst scenario (Scenario 4) must use `datetime.now(timezone.utc)` timestamps so the in-memory 5-minute filter in `DetectionContext` includes all 20 events
- TTL field verification (Property 1, Requirement 7.6) must account for the fact that `ttl` is set by the handler, not `parse_cloudtrail_event` — integration tests must call handler-level logic or set TTL explicitly after normalization
- SNS message assertion uses an SQS queue subscribed to the mocked SNS topic — this is the correct moto pattern for inspecting published messages
