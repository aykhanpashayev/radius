# Implementation Plan: Phase 4 Detection Rules and Incident Logic

## Overview

Phase 4 replaces the Detection_Engine placeholder with a real, rule-based detection engine. All work is additive — no Phase 2 or Phase 3 infrastructure, tables, or APIs are modified.

**Implementation Language:** Python 3.11

**Key Deliverables:**
- `DetectionContext` data fetcher
- Extended `DetectionRule` interface + `ContextAwareDetectionRule`
- `RuleEngine` orchestrator
- 7 concrete detection rules
- Rewritten `Detection_Engine` handler (real logic, same interface)
- Unit and property-based tests
- Detection rules documentation

**Important Constraints:**
- Do NOT modify DynamoDB table definitions
- Do NOT modify existing API endpoints
- Do NOT change the `lambda_handler` signature or return shape
- Do NOT modify Incident_Processor
- Preserve all Phase 2 and Phase 3 Lambda invocation chains

**Priority Labels:**
- **must-have**: Required for Phase 4 functionality
- **should-have**: Important but not blocking
- **nice-to-have**: Optional enhancements

---

## Tasks

### Milestone 1: Detection Foundation

- [x] 1. Extend DetectionRule interface and add ContextAwareDetectionRule (must-have)
  - Update `backend/functions/detection_engine/interfaces.py`
  - Add `severity: str` and `rule_id: str` class attributes to `DetectionRule` ABC
  - Add `ContextAwareDetectionRule(DetectionRule)` ABC with `evaluate_with_context(event_summary, context) -> Finding | None`
  - Keep existing `Finding` dataclass and `evaluate()` signature unchanged
  - Add forward reference guard for `DetectionContext` to avoid circular imports
  - **Deliverable:** Updated `interfaces.py` with extended rule contracts
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Implement DetectionContext (must-have)
  - Create `backend/functions/detection_engine/context.py`
  - Define `DetectionContext` dataclass with fields: `identity_arn`, `recent_events_60m`, `recent_events_5m`, `services_30d`
  - Implement `DetectionContext.build(identity_arn, event_summary_table)` classmethod
  - Query Event_Summary for events in last 60 minutes (for IAMPolicyModificationSpike)
  - Query Event_Summary for events in last 5 minutes (for APIBurstAnomaly)
  - Query Event_Summary for last 30 days, extract distinct service prefixes (for UnusualServiceUsage)
  - Use `get_dynamodb_client()` from `backend/common/dynamodb_utils.py`
  - Handle DynamoDB exceptions: log warning and return empty collections
  - **Deliverable:** `DetectionContext` with `build()` factory
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 3. Implement RuleEngine (must-have)
  - Create `backend/functions/detection_engine/engine.py`
  - Define `RuleEngine` class with `rules: list[DetectionRule]` attribute
  - Implement `evaluate(event_summary: dict, context: DetectionContext) -> list[Finding]`
  - For each rule: if `ContextAwareDetectionRule`, call `evaluate_with_context()`; else call `evaluate()`
  - Catch all exceptions per rule, log warning with `rule_id`, continue to next rule
  - Return list of all non-None findings
  - **Deliverable:** `RuleEngine` that orchestrates all 7 rules
  - _Requirements: 2.1, 2.2, 2.4_

- [x] 4. Create rules package skeleton (must-have)
  - Create `backend/functions/detection_engine/rules/` directory
  - Create `backend/functions/detection_engine/rules/__init__.py` that exports `ALL_RULES` list
  - **Deliverable:** Rules package ready for rule implementations
  - _Requirements: 2.1_

### Milestone 2: Detection Rules Implementation

- [x] 5. Implement PrivilegeEscalation rule (must-have)
  - Create `backend/functions/detection_engine/rules/privilege_escalation.py`
  - Define `PrivilegeEscalationRule(ContextAwareDetectionRule)` with `rule_id = "privilege_escalation"`, `severity = "High"`, `confidence = 80`
  - Trigger on: `CreatePolicyVersion`, `AddUserToGroup`, `PassRole` (single event)
  - Trigger on: `AttachUserPolicy` when `CreateUser` appears in `context.recent_events_60m`
  - Return `Finding` with `description` naming the specific escalation action
  - Return `None` if no trigger condition met
  - **Deliverable:** `PrivilegeEscalationRule` implementation
  - _Requirements: 3.1, 3.2, 3.3_

- [x] 6. Implement IAMPolicyModificationSpike rule (must-have)
  - Create `backend/functions/detection_engine/rules/iam_policy_modification_spike.py`
  - Define `IAMPolicyModificationSpikeRule(ContextAwareDetectionRule)` with `rule_id = "iam_policy_modification_spike"`, `severity = "High"`, `confidence = 75`
  - Count events in `context.recent_events_60m` whose event name is in the IAM mutation set
  - Trigger if count >= 5
  - Return `Finding` with description including the mutation count
  - **Deliverable:** `IAMPolicyModificationSpikeRule` implementation
  - _Requirements: 3.4, 3.5, 3.6, 3.7_

- [x] 7. Implement CrossAccountRoleAssumption rule (must-have)
  - Create `backend/functions/detection_engine/rules/cross_account_role_assumption.py`
  - Define `CrossAccountRoleAssumptionRule(DetectionRule)` with `rule_id = "cross_account_role_assumption"`, `severity = "Moderate"`, `confidence = 70`
  - Trigger when event name is `AssumeRole` AND `event_parameters.roleArn` account differs from identity account
  - Use `extract_account_id()` from `backend/common/aws_utils.py`
  - Return `Finding` with description including source and target account IDs
  - **Deliverable:** `CrossAccountRoleAssumptionRule` implementation
  - _Requirements: 3.8, 3.9, 3.10_

- [x] 8. Implement LoggingDisruption rule (must-have)
  - Create `backend/functions/detection_engine/rules/logging_disruption.py`
  - Define `LoggingDisruptionRule(DetectionRule)` with `rule_id = "logging_disruption"`, `severity = "Critical"`, `confidence = 95`
  - Trigger when event name is in: `{StopLogging, DeleteTrail, UpdateTrail, PutEventSelectors, DeleteFlowLogs, DeleteLogGroup, DeleteLogStream}`
  - Return `Finding` with description naming the specific action
  - **Deliverable:** `LoggingDisruptionRule` implementation
  - _Requirements: 3.11, 3.12, 3.13_

- [x] 9. Implement RootUserActivity rule (must-have)
  - Create `backend/functions/detection_engine/rules/root_user_activity.py`
  - Define `RootUserActivityRule(DetectionRule)` with `rule_id = "root_user_activity"`, `severity = "Very High"`, `confidence = 100`
  - Trigger when `identity_arn` contains `"root"` (case-insensitive) OR `identity_type == "Root"`
  - Return `Finding` with description stating root account activity was detected
  - **Deliverable:** `RootUserActivityRule` implementation
  - _Requirements: 3.14, 3.15, 3.16_

- [x] 10. Implement APIBurstAnomaly rule (must-have)
  - Create `backend/functions/detection_engine/rules/api_burst_anomaly.py`
  - Define `APIBurstAnomalyRule(ContextAwareDetectionRule)` with `rule_id = "api_burst_anomaly"`, `severity = "Moderate"`, `confidence = 65`
  - Trigger when `len(context.recent_events_5m) >= 20`
  - Return `Finding` with description including call count and "last 5 minutes"
  - **Deliverable:** `APIBurstAnomalyRule` implementation
  - _Requirements: 3.17, 3.18, 3.19_

- [x] 11. Implement UnusualServiceUsage rule (must-have)
  - Create `backend/functions/detection_engine/rules/unusual_service_usage.py`
  - Define `UnusualServiceUsageRule(ContextAwareDetectionRule)` with `rule_id = "unusual_service_usage"`, `severity = "Low"`, `confidence = 60`
  - High-risk service set: `{"sts", "iam", "organizations", "kms", "secretsmanager", "ssm"}`
  - Extract current service from `event_type` by splitting on `:`
  - Trigger when current service is in high-risk set AND not in `context.services_30d`
  - Return `Finding` with description naming the new service
  - **Deliverable:** `UnusualServiceUsageRule` implementation
  - _Requirements: 3.20, 3.21, 3.22_

### Milestone 3: Detection_Engine Handler

- [x] 12. Rewrite Detection_Engine handler with real detection logic (must-have)
  - Update `backend/functions/detection_engine/handler.py`
  - Import `RuleEngine` from `engine.py` and `DetectionContext` from `context.py`
  - Instantiate `RuleEngine` once at module level (Lambda warm-start reuse)
  - In `lambda_handler`: extract `identity_arn` and `event_summary_table` from env
  - Call `DetectionContext.build(identity_arn, event_summary_table)`
  - Call `engine.evaluate(event, det_context)` to get findings list
  - For each finding: invoke Incident_Processor async (`InvocationType="Event"`)
  - Track `forwarded` and `failures` counts
  - Return `{"status": "ok", "findings": forwarded, "failures": failures}` — remove `"placeholder": True`
  - Handle invocation errors: log and continue (do not raise)
  - **Deliverable:** Detection_Engine handler with real logic, same external interface
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 5.1, 5.3, 5.4_

### Milestone 4: Testing

- [x] 13. Write unit tests for DetectionContext (must-have)
  - Create `backend/tests/test_detection_context.py`
  - Mock DynamoDB using `unittest.mock.patch`
  - Test `build()` returns correct fields from mocked responses
  - Test `recent_events_60m` contains only events within last 60 minutes
  - Test `recent_events_5m` contains only events within last 5 minutes
  - Test `services_30d` extracts correct service prefixes from event types
  - Test DynamoDB exception returns empty collections (no crash)
  - **Deliverable:** Unit tests for `DetectionContext.build()`
  - _Requirements: 4.1, 4.2_

- [x] 14. Write unit tests for all 7 detection rules (must-have)
  - Create `backend/tests/test_detection_rules.py`
  - For each rule test:
    - No-trigger case: event that should NOT fire the rule → returns `None`
    - Trigger case: event that SHOULD fire the rule → returns `Finding`
    - Finding fields: `detection_type == rule.rule_id`, `severity` correct, `confidence` correct
    - Edge cases specific to each rule (e.g. same-account AssumeRole, root ARN variants)
  - Use synthetic Event_Summary dicts and DetectionContext objects — no DynamoDB calls
  - **Deliverable:** Unit tests covering all 7 rules
  - _Requirements: 7.1, 7.2_

- [x] 15. Write unit tests for RuleEngine and handler (must-have)
  - Create `backend/tests/test_detection_engine.py`
  - Test RuleEngine: multiple rules firing returns all findings
  - Test RuleEngine: rule exception is caught, other rules still evaluated
  - Test RuleEngine: no rules fire returns empty list
  - Test handler: findings forwarded to Incident_Processor
  - Test handler: invocation failure logged, other findings still forwarded
  - Test handler: zero findings returns `{"status": "ok", "findings": 0, "failures": 0}`
  - **Deliverable:** Unit tests for `RuleEngine` and `lambda_handler`
  - _Requirements: 7.4_

- [x] 16. Write property-based tests for detection correctness (must-have)
  - Create `backend/tests/test_detection_properties.py`
  - Add `hypothesis` to `backend/functions/detection_engine/requirements.txt`
  - Implement Hypothesis strategies: `event_summary_strategy`, `detection_context_strategy`
  - **Property 1 — Finding validity**: every Finding has non-empty `identity_arn`, `detection_type`, valid `severity`
  - **Property 2 — Confidence bounds**: `0 <= confidence <= 100` for all findings
  - **Property 3 — Rule identity**: `finding.detection_type == rule.rule_id`
  - **Property 4 — No unhandled exceptions**: rules never raise on arbitrary event input
  - **Property 5 — Determinism**: same event + context always produces same findings
  - **Property 6 — No false positives on empty input**: empty event dict never triggers any rule
  - **Property 7 — Known triggers always fire**: known trigger inputs always produce a Finding
  - **Deliverable:** Property-based test suite validating all 7 correctness properties
  - _Requirements: 7.3_

### Milestone 5: Documentation

- [x] 17. Write detection rules documentation (must-have)
  - Create `docs/detection-rules.md` (replaces stub at `docs/detections/detection-rules.md`)
  - Document each of the 7 rules: `rule_id`, `rule_name`, severity, confidence, trigger conditions, example triggering event
  - Document the two rule types: single-event vs context-aware
  - Document the detection pipeline flow
  - Document deduplication behavior (handled by Incident_Processor, 24h window)
  - **Deliverable:** `docs/detection-rules.md` with complete detection reference
  - _Requirements: 8.1, 8.2_

---

## Notes

**Task Organization:**
- Milestone 1: Detection Foundation (4 tasks — interfaces, context, engine, rules package)
- Milestone 2: Detection Rules (7 tasks — one per rule)
- Milestone 3: Handler (1 task — handler rewrite)
- Milestone 4: Testing (4 tasks — context tests, rule tests, engine tests, property tests)
- Milestone 5: Documentation (1 task — detection rules doc)

**Key Architecture Decisions:**
- `RuleEngine` instantiated at module level in `handler.py` for Lambda warm-start reuse
- Single-event rules (`DetectionRule`) receive only the Event_Summary dict — no DynamoDB calls
- Context-aware rules (`ContextAwareDetectionRule`) receive pre-fetched `DetectionContext`
- `DetectionContext.build()` is the single point of DynamoDB reads, making rules fully testable
- `extract_account_id()` and `extract_event_name()` imported from `backend/common/aws_utils.py`
- No new DynamoDB tables, GSIs, or Terraform changes required
- Incident_Processor handles all deduplication — Detection_Engine forwards all findings

**Correctness Properties (from Requirement 7):**
All 7 properties are validated by property-based tests in Task 16.

**No Infrastructure Changes:**
Detection_Engine already has `ReadEventSummary` IAM permissions (added in Phase 2). No `iam.tf` or `main.tf` changes are needed.
