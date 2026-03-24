# Requirements Document — Phase 6: Testing and Documentation

## Introduction

Phase 6 brings Radius to production quality by establishing a comprehensive integration test suite and completing all user-facing documentation. The phase covers end-to-end pipeline validation, attack scenario simulation, detection rule accuracy verification, scoring correctness validation, DynamoDB write verification, and a full documentation refresh across architecture, deployment, scoring model, detection rules, and dashboard usage.

All work is additive — no existing Lambda handler signatures, DynamoDB table definitions, API contracts, or Terraform module interfaces are modified.

---

## Glossary

- **Event_Normalizer**: Lambda function that receives CloudTrail events from EventBridge, normalizes them, and fans out to Detection_Engine and Identity_Collector.
- **Detection_Engine**: Lambda function that evaluates detection rules against normalized events and forwards findings to Incident_Processor.
- **Score_Engine**: Lambda function that calculates the Blast Radius Score for an IAM identity.
- **Incident_Processor**: Lambda function that creates or deduplicates Incident records and publishes SNS alerts.
- **Identity_Collector**: Lambda function that maintains Identity_Profile and Trust_Relationship records.
- **API_Handler**: Lambda function that serves the REST API via API Gateway.
- **Blast_Radius_Score**: DynamoDB table storing the current score snapshot per identity.
- **Identity_Profile**: DynamoDB table storing one record per observed IAM identity.
- **Incident**: DynamoDB table storing security incidents.
- **Event_Summary**: DynamoDB table storing normalized CloudTrail event records.
- **Trust_Relationship**: DynamoDB table storing trust edges between IAM identities.
- **Finding**: Dataclass produced by a detection rule, forwarded to Incident_Processor.
- **ScoringContext**: Dataclass holding pre-fetched identity data used by Score_Engine rules.
- **DetectionContext**: Dataclass holding pre-fetched recent events used by context-aware detection rules.
- **Integration_Test**: A pytest test that exercises multiple real components together using moto or localstack for AWS service mocking.
- **Attack_Scenario**: A sequence of CloudTrail events that simulates a realistic identity-based attack pattern.
- **inject-events.py**: Script that injects sample CloudTrail events into EventBridge for manual pipeline testing.
- **moto**: Python library that mocks AWS services (DynamoDB, Lambda, SNS, EventBridge) in-process for testing.

---

## Requirements

### Requirement 1: Integration Test Infrastructure

**User Story:** As a developer, I want a reusable integration test harness, so that I can test multiple pipeline components together without deploying to AWS.

#### Acceptance Criteria

1. THE Integration_Test suite SHALL use moto to mock DynamoDB, Lambda, and SNS without requiring live AWS credentials.
2. WHEN the integration test suite initialises, THE Test_Harness SHALL create all five DynamoDB tables (Identity_Profile, Blast_Radius_Score, Incident, Event_Summary, Trust_Relationship) with their correct primary keys and GSI definitions.
3. THE Test_Harness SHALL provide a reusable pytest fixture that creates and tears down mocked AWS resources for each test function.
4. WHEN a test function completes, THE Test_Harness SHALL destroy all mocked resources so that no state leaks between test functions.
5. THE Integration_Test suite SHALL be runnable with `pytest backend/tests/integration/` without any live AWS environment variables set.

---

### Requirement 2: Event Pipeline End-to-End Validation

**User Story:** As a developer, I want end-to-end tests for the event processing pipeline, so that I can verify that a CloudTrail event flows correctly from Event_Normalizer through to DynamoDB writes.

#### Acceptance Criteria

1. WHEN a valid CloudTrail event is passed to Event_Normalizer, THE Integration_Test SHALL verify that a corresponding Event_Summary record is written to the Event_Summary DynamoDB table.
2. WHEN a valid CloudTrail event is passed to Event_Normalizer, THE Integration_Test SHALL verify that a corresponding Identity_Profile record is created or updated in the Identity_Profile DynamoDB table.
3. WHEN an `sts:AssumeRole` CloudTrail event is passed to Event_Normalizer, THE Integration_Test SHALL verify that a Trust_Relationship record is written to the Trust_Relationship DynamoDB table.
4. WHEN Event_Normalizer processes an event, THE Integration_Test SHALL verify that Detection_Engine is invoked with the normalized Event_Summary payload.
5. WHEN Event_Normalizer processes an event, THE Integration_Test SHALL verify that Identity_Collector is invoked with the normalized Event_Summary payload.
6. IF a CloudTrail event is missing required fields (`eventName`, `userIdentity`, `eventTime`), THEN THE Event_Normalizer SHALL return an error response without writing any DynamoDB records.

---

### Requirement 3: Detection Rule Accuracy

**User Story:** As a security engineer, I want integration tests that verify detection rule accuracy against realistic CloudTrail events, so that I can confirm rules fire correctly on real event shapes.

#### Acceptance Criteria

1. WHEN the `suspicious-privilege-escalation.json` sample event is processed, THE Integration_Test SHALL verify that the `privilege_escalation` detection rule produces a Finding.
2. WHEN the `suspicious-cross-account-access.json` sample event is processed, THE Integration_Test SHALL verify that the `cross_account_role_assumption` detection rule produces a Finding.
3. WHEN a `cloudtrail:StopLogging` event is processed, THE Integration_Test SHALL verify that the `logging_disruption` detection rule produces a Finding with severity `Critical`.
4. WHEN a `Root`-typed identity event is processed, THE Integration_Test SHALL verify that the `root_user_activity` detection rule produces a Finding with severity `Very High`.
5. WHEN a benign `iam:ListUsers` event is processed with no suspicious context, THE Integration_Test SHALL verify that zero Findings are produced.
6. FOR ALL detection rules, WHEN a rule produces a Finding, THE Integration_Test SHALL verify that `finding.detection_type` equals the rule's `rule_id`.
7. FOR ALL detection rules, WHEN a rule produces a Finding, THE Integration_Test SHALL verify that `finding.confidence` is an integer in the range 0 to 100 inclusive.

---

### Requirement 4: Scoring Correctness Validation

**User Story:** As a security engineer, I want integration tests that verify the Score_Engine produces correct scores for known identity profiles, so that I can confirm the scoring model behaves as documented.

#### Acceptance Criteria

1. WHEN Score_Engine is invoked with a ScoringContext containing only IAM write events, THE Integration_Test SHALL verify that the resulting `score_value` is greater than 0 and `severity_level` is not `Low`.
2. WHEN Score_Engine is invoked with an empty ScoringContext (no events, no trusts, no incidents), THE Integration_Test SHALL verify that `score_value` equals 0 and `severity_level` equals `Low`.
3. WHEN Score_Engine is invoked with a ScoringContext containing a `cloudtrail:StopLogging` event, THE Integration_Test SHALL verify that the `LoggingDisruption` contributing factor appears in `contributing_factors` with a value of `+20`.
4. WHEN Score_Engine is invoked with a ScoringContext containing cross-account trust relationships, THE Integration_Test SHALL verify that the `CrossAccountTrust` contributing factor appears in `contributing_factors`.
5. FOR ALL valid ScoringContext inputs, THE Score_Engine SHALL produce a `score_value` in the range 0 to 100 inclusive.
6. FOR ALL valid ScoringContext inputs, THE Score_Engine SHALL produce a `severity_level` that is consistent with the `score_value` according to the documented severity thresholds (0–19 Low, 20–39 Moderate, 40–59 High, 60–79 Very High, 80–100 Critical).
7. WHEN Score_Engine writes a result, THE Integration_Test SHALL verify that a Blast_Radius_Score record is written to DynamoDB with the correct `identity_arn`, `score_value`, and `severity_level` fields.

---

### Requirement 5: Attack Scenario Simulation

**User Story:** As a security engineer, I want integration tests that simulate complete attack scenarios, so that I can verify the full pipeline responds correctly to realistic threat patterns.

#### Acceptance Criteria

1. WHEN the privilege escalation attack scenario is simulated (CreateUser followed by AttachUserPolicy for the same identity within 60 minutes), THE Integration_Test SHALL verify that an Incident record with `detection_type` equal to `privilege_escalation` is created in the Incident DynamoDB table.
2. WHEN the cross-account lateral movement scenario is simulated (AssumeRole targeting a role in a different account), THE Integration_Test SHALL verify that an Incident record with `detection_type` equal to `cross_account_role_assumption` is created in the Incident DynamoDB table.
3. WHEN the logging disruption scenario is simulated (StopLogging event), THE Integration_Test SHALL verify that an Incident record with `severity` equal to `Critical` is created in the Incident DynamoDB table.
4. WHEN the API burst scenario is simulated (20 or more API calls within 5 minutes for the same identity), THE Integration_Test SHALL verify that an Incident record with `detection_type` equal to `api_burst_anomaly` is created in the Incident DynamoDB table.
5. WHEN the root user activity scenario is simulated (any event with `identity_type` equal to `Root`), THE Integration_Test SHALL verify that an Incident record with `detection_type` equal to `root_user_activity` is created in the Incident DynamoDB table.
6. WHEN the same attack scenario fires twice for the same identity within 24 hours, THE Integration_Test SHALL verify that only one Incident record exists (deduplication enforced by Incident_Processor).

---

### Requirement 6: Incident Generation Validation

**User Story:** As a developer, I want integration tests that verify Incident_Processor creates well-formed Incident records, so that I can confirm the incident lifecycle is correct.

#### Acceptance Criteria

1. WHEN Incident_Processor receives a valid Finding, THE Integration_Test SHALL verify that the created Incident record contains all required fields: `incident_id`, `identity_arn`, `detection_type`, `severity`, `confidence`, `status`, `creation_timestamp`, `update_timestamp`, `related_event_ids`, and `status_history`.
2. WHEN Incident_Processor creates a new Incident, THE Integration_Test SHALL verify that the initial `status` is `open`.
3. WHEN Incident_Processor creates a new Incident, THE Integration_Test SHALL verify that `status_history` contains exactly one entry with `status` equal to `open`.
4. WHEN Incident_Processor receives a duplicate Finding (same `identity_arn` and `detection_type` within 24 hours), THE Integration_Test SHALL verify that no new Incident record is created and the existing record's `related_event_ids` is updated.
5. WHEN a Finding has severity `High`, `Very High`, or `Critical`, THE Integration_Test SHALL verify that Incident_Processor publishes an SNS alert to the Alert_Topic.
6. WHEN a Finding has severity `Low` or `Moderate`, THE Integration_Test SHALL verify that Incident_Processor does not publish an SNS alert.
7. WHEN an Incident status is transitioned from `open` to `investigating`, THE Integration_Test SHALL verify that `status_history` contains two entries and `update_timestamp` is updated.

---

### Requirement 7: DynamoDB Write Verification

**User Story:** As a developer, I want integration tests that verify all DynamoDB writes are structurally correct, so that I can confirm data integrity across all five tables.

#### Acceptance Criteria

1. WHEN Event_Normalizer writes an Event_Summary record, THE Integration_Test SHALL verify that the record contains `identity_arn`, `timestamp`, `event_id`, `event_type`, `date_partition`, and `ttl` fields.
2. WHEN Identity_Collector writes an Identity_Profile record, THE Integration_Test SHALL verify that the record contains `identity_arn`, `identity_type`, `account_id`, and `last_activity_timestamp` fields.
3. WHEN Identity_Collector writes a Trust_Relationship record, THE Integration_Test SHALL verify that the record contains `source_arn`, `target_arn`, `relationship_type`, `source_account_id`, and `target_account_id` fields.
4. WHEN Score_Engine writes a Blast_Radius_Score record, THE Integration_Test SHALL verify that `score_value` is a number in the range 0 to 100 inclusive and `severity_level` is one of `Low`, `Moderate`, `High`, `Very High`, `Critical`.
5. WHEN Incident_Processor writes an Incident record, THE Integration_Test SHALL verify that `incident_id` is a valid UUID v4 string.
6. WHEN Event_Normalizer writes an Event_Summary record, THE Integration_Test SHALL verify that the `ttl` field is set to a Unix epoch value approximately 90 days in the future (within a 60-second tolerance).
7. FOR ALL DynamoDB writes, THE Integration_Test SHALL verify that no write operation raises an unhandled exception for well-formed input.

---

### Requirement 8: Architecture Documentation

**User Story:** As a developer or operator, I want an up-to-date architecture overview, so that I can understand how all Radius components fit together.

#### Acceptance Criteria

1. THE `docs/architecture.md` file SHALL describe the complete event processing pipeline from CloudTrail through EventBridge, Event_Normalizer, Detection_Engine, Incident_Processor, Identity_Collector, Score_Engine, and API_Handler.
2. THE `docs/architecture.md` file SHALL include a text-based pipeline diagram showing the invocation chain and data flow between all Lambda functions.
3. THE `docs/architecture.md` file SHALL document all five DynamoDB tables with their primary keys and purpose.
4. THE `docs/architecture.md` file SHALL document all six Lambda functions with their trigger, purpose, and downstream invocations.
5. THE `docs/architecture.md` file SHALL document the Terraform module structure and the dependencies between modules.
6. THE `docs/architecture.md` file SHALL document the design principles: serverless, event-driven, cost-aware, explainable, and multi-account.

---

### Requirement 9: Deployment Documentation

**User Story:** As an operator, I want a complete deployment guide, so that I can deploy Radius to a new AWS environment without prior knowledge of the codebase.

#### Acceptance Criteria

1. THE `docs/deployment.md` file SHALL document all prerequisites: AWS CLI version, Terraform version, Python version, and required IAM permissions.
2. THE `docs/deployment.md` file SHALL provide step-by-step instructions for first-time setup including S3 state bucket creation, backend configuration, and variable configuration.
3. THE `docs/deployment.md` file SHALL document the `build-lambdas.sh` script usage with all supported flags.
4. THE `docs/deployment.md` file SHALL document the `deploy-infra.sh` script usage including plan-only mode and auto-approve mode.
5. THE `docs/deployment.md` file SHALL document the `verify-deployment.sh` script and what it checks.
6. THE `docs/deployment.md` file SHALL document the differences between dev and prod environment configurations.
7. THE `docs/deployment.md` file SHALL document the rollback procedure using Terraform state versioning in S3.
8. THE `docs/deployment.md` file SHALL document at least three common troubleshooting scenarios with resolution steps.

---

### Requirement 10: Scoring Model Documentation

**User Story:** As a security analyst, I want a clear explanation of the Blast Radius Score, so that I can understand why an identity received a particular score.

#### Acceptance Criteria

1. THE `docs/scoring-model.md` file SHALL document all eight scoring rules with their `rule_id`, `max_contribution`, trigger conditions, and point values.
2. THE `docs/scoring-model.md` file SHALL document the five severity thresholds with their score ranges: 0–19 Low, 20–39 Moderate, 40–59 High, 60–79 Very High, 80–100 Critical.
3. THE `docs/scoring-model.md` file SHALL include a worked example showing a complete score calculation with all contributing factors listed.
4. THE `docs/scoring-model.md` file SHALL document the `contributing_factors` field format (`"<rule_name>: +<points>"`).
5. THE `docs/scoring-model.md` file SHALL document the two invocation modes: single-identity mode and batch mode, including their trigger payloads.
6. THE `docs/scoring-model.md` file SHALL document the data sources used by ScoringContext: Identity_Profile, Event_Summary (last 90 days, max 1,000 events), Trust_Relationship, and Incident tables.

---

### Requirement 11: Detection Rule Documentation

**User Story:** As a security engineer, I want complete detection rule documentation, so that I can understand what each rule detects, tune thresholds, and reduce false positives.

#### Acceptance Criteria

1. THE `docs/detection-rules.md` file SHALL document all seven detection rules with their `rule_id`, `rule_name`, severity, confidence, rule type (single-event or context-aware), and trigger conditions.
2. THE `docs/detection-rules.md` file SHALL include an example triggering event or context for each rule.
3. THE `docs/detection-rules.md` file SHALL document the deduplication behavior: 24-hour window keyed on `identity_arn` + `detection_type`.
4. THE `docs/detection-rules.md` file SHALL document the DetectionContext data sources: `recent_events_60m` (one DynamoDB query) and `prior_services_30d` (one DynamoDB query excluding the current event).
5. THE `docs/detection-rules.md` file SHALL include a summary table listing all seven rules with their severity and confidence values.
6. THE `docs/detection-rules.md` file SHALL document the five severity levels and their operational meaning.

---

### Requirement 12: Dashboard Usage Documentation

**User Story:** As a security analyst, I want a dashboard usage guide, so that I can navigate the Radius UI and act on security findings effectively.

#### Acceptance Criteria

1. THE `docs/dashboard.md` file SHALL document all dashboard pages: Identity List, Identity Detail, Incident List, Incident Detail, and Score Overview.
2. THE `docs/dashboard.md` file SHALL document how to filter identities by severity level and account ID.
3. THE `docs/dashboard.md` file SHALL document how to update an incident status (open → investigating → resolved or false_positive) from the UI.
4. THE `docs/dashboard.md` file SHALL document the Blast Radius Score display including the severity colour coding and contributing factors breakdown.
5. THE `docs/dashboard.md` file SHALL document the local development setup: `npm install`, `npm run dev`, and the `VITE_API_BASE_URL` environment variable.
6. THE `docs/dashboard.md` file SHALL document the production build and S3 deployment steps including CloudFront cache invalidation.

---

### Requirement 13: Developer Contribution Guide

**User Story:** As a new contributor, I want a developer guide, so that I can add new detection rules or scoring rules without breaking existing behaviour.

#### Acceptance Criteria

1. THE `docs/developer-guide.md` file SHALL document the steps to add a new detection rule: create the rule file, implement the `DetectionRule` or `ContextAwareDetectionRule` interface, register in `rules/__init__.py`, and add unit tests.
2. THE `docs/developer-guide.md` file SHALL document the steps to add a new scoring rule: create the rule file, implement the `ScoringRule` interface, register in `rules/__init__.py`, and add unit tests.
3. THE `docs/developer-guide.md` file SHALL document the test structure: `backend/tests/` contains unit tests and property-based tests; `backend/tests/integration/` contains integration tests.
4. THE `docs/developer-guide.md` file SHALL document how to run the full test suite locally using `pytest`.
5. THE `docs/developer-guide.md` file SHALL document how to inject sample events using `scripts/inject-events.py` for manual pipeline testing.
6. THE `docs/developer-guide.md` file SHALL document the Lambda packaging and deployment workflow using `build-lambdas.sh` and `deploy-infra.sh`.
