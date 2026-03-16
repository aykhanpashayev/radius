# Phase 4 Requirements: Detection Rules and Incident Logic

## Overview

Phase 4 replaces the Detection_Engine placeholder with real, deterministic detection rules. The engine analyzes normalized CloudTrail events and generates Incident records when suspicious identity behavior is detected. All work is additive — no Phase 2 or Phase 3 infrastructure, tables, or APIs are modified.

---

## Constraints

- Do NOT modify DynamoDB table definitions or GSI configurations
- Do NOT modify existing API endpoints or Lambda handler signatures
- Do NOT change the Incident_Processor interface or `Finding` dataclass fields
- Preserve all Phase 2 and Phase 3 Lambda invocation chains
- Detection rules must be deterministic and explainable — no ML or probabilistic models
- All detection must remain event-driven and cost-aware

---

## Requirement 1: Detection Rule Interface

**1.1** The `DetectionRule` ABC in `interfaces.py` must define `rule_id: str`, `rule_name: str`, and `severity: str` class attributes.

**1.2** The `evaluate(event_summary: dict) -> Finding | None` method must return a `Finding` when the rule triggers, or `None` when it does not.

**1.3** The `Finding` dataclass must include: `identity_arn`, `detection_type`, `severity`, `confidence`, `related_event_ids`, `description`, and `metadata`.

**1.4** Rules must be stateless — each `evaluate()` call receives a single normalized Event_Summary dict and must not perform DynamoDB reads.

**1.5** Rules that require historical context (e.g. burst detection) must receive pre-fetched context via a `DetectionContext` object, not perform their own DynamoDB queries.

---

## Requirement 2: Detection Engine

**2.1** The Detection_Engine must instantiate all rules once at module level (Lambda warm-start reuse).

**2.2** For each incoming Event_Summary, the engine must evaluate all applicable rules and collect all triggered findings.

**2.3** Each triggered finding must be forwarded to Incident_Processor via async Lambda invocation (`InvocationType="Event"`).

**2.4** If a rule raises an exception during evaluation, the engine must log the error and continue evaluating remaining rules.

**2.5** The handler must return `{"status": "ok", "findings": N, "failures": M}` where N is the count of findings forwarded and M is the count of rule evaluation errors.

**2.6** The `"placeholder": True` field must be removed from the handler response.

---

## Requirement 3: Detection Rules

### Rule 1 — PrivilegeEscalation

**3.1** Trigger on any of these direct single-event indicators: `CreatePolicyVersion`, `AddUserToGroup`, `PassRole`.

**3.2** Also trigger on `AttachUserPolicy` when `CreateUser` appears in `context.recent_events_60m` (combined indicator requiring context).

**3.3** `PrivilegeEscalation` is a **context-aware rule** (`ContextAwareDetectionRule`) because the combined `CreateUser` + `AttachUserPolicy` indicator requires checking recent prior events.

**3.4** Severity: **High**. Confidence: 80.

**3.5** Description must name the specific escalation action or pattern observed.

### Rule 2 — IAMPolicyModificationSpike

**3.4** Trigger when the identity has performed 5 or more IAM mutation events within the last 60 minutes (queried from Event_Summary via DetectionContext).

**3.5** IAM mutation events: `AttachUserPolicy`, `AttachRolePolicy`, `AttachGroupPolicy`, `PutUserPolicy`, `PutRolePolicy`, `PutGroupPolicy`, `CreatePolicyVersion`, `SetDefaultPolicyVersion`, `AddUserToGroup`.

**3.6** Severity: **High**. Confidence: 75.

**3.7** Description must include the mutation count observed.

### Rule 3 — CrossAccountRoleAssumption

**3.8** Trigger when an `AssumeRole` event targets a role in a different AWS account than the identity's account.

**3.9** Severity: **Moderate**. Confidence: 70.

**3.10** Description must include the source account and target account IDs.

### Rule 4 — LoggingDisruption

**3.11** Trigger when any of the following events are observed: `StopLogging`, `DeleteTrail`, `UpdateTrail`, `PutEventSelectors`, `DeleteFlowLogs`, `DeleteLogGroup`, `DeleteLogStream`.

**3.12** Severity: **Critical**. Confidence: 95.

**3.13** Description must name the specific disruption action observed.

### Rule 5 — RootUserActivity

**3.14** Trigger when the `identity_arn` contains `root` or the `identity_type` is `Root`.

**3.15** Severity: **Very High**. Confidence: 100.

**3.16** Description must state that root account activity was detected.

### Rule 6 — APIBurstAnomaly

**3.17** Trigger when the identity has made 20 or more API calls within the last 5 minutes (queried from Event_Summary via DetectionContext).

**3.18** Severity: **Moderate**. Confidence: 65.

**3.19** Description must include the call count and time window.

### Rule 7 — UnusualServiceUsage

**3.20** Trigger when the identity accesses a service it has not used in the prior 30 days, AND the service is in a high-risk set: `{sts, iam, organizations, kms, secretsmanager, ssm}`.

**3.21** Severity: **Low**. Confidence: 60.

**3.22** Description must name the new service accessed.

---

## Requirement 4: DetectionContext

**4.1** A `DetectionContext` dataclass must hold pre-fetched data: `recent_events_60m` (events in last 60 minutes), and `prior_services_30d` (distinct services used in events strictly before the current event timestamp).

**4.2** `recent_events_5m` must be derived in-memory from `recent_events_60m` as a property — no separate DynamoDB query.

**4.3** `DetectionContext.build(identity_arn, current_event_id, current_event_timestamp, event_summary_table)` must perform exactly two DynamoDB queries: one for the last 60 minutes, one for the last 30 days with `timestamp < current_event_timestamp`.

**4.4** The 30-day query must exclude the current event by filtering `timestamp < current_event_timestamp`. The current event's `event_id` must also be excluded as a safety guard. This ensures `prior_services_30d` never contains the current event's service, making UnusualServiceUsage work correctly.

**4.5** Single-event rules (CrossAccountRoleAssumption, LoggingDisruption, RootUserActivity) must not use `DetectionContext` — they operate on the Event_Summary dict only.

**4.6** Context-aware rules (PrivilegeEscalation, IAMPolicyModificationSpike, APIBurstAnomaly, UnusualServiceUsage) must receive `DetectionContext` as a parameter to `evaluate_with_context()`.

---

## Requirement 5: Incident Integration

**5.1** Each `Finding` produced by a detection rule must be forwarded to Incident_Processor as-is — no transformation of the `Finding` fields.

**5.2** The Incident_Processor's existing deduplication logic (24-hour window, same `identity_arn` + `detection_type`) must handle duplicate suppression — Detection_Engine must not implement its own deduplication.

**5.3** The `detection_type` field in the Finding must equal the rule's `rule_id`.

**5.4** The `related_event_ids` field must contain the `event_id` of the triggering Event_Summary.

---

## Requirement 6: Severity Levels

**6.1** All five severity levels must be used across the 7 rules: Low, Moderate, High, Very High, Critical.

**6.2** Severity assignments must match the definitions in Requirement 3.

**6.3** The `confidence` field must be an integer 0–100 representing rule certainty.

---

## Requirement 7: Testing

**7.1** Unit tests must cover each of the 7 detection rules: no-trigger case, trigger case, and edge cases.

**7.2** Unit tests must use synthetic Event_Summary dicts — no DynamoDB calls.

**7.3** Property-based tests must validate: findings always have valid severity levels, `confidence` is always 0–100, `detection_type` always equals the rule's `rule_id`, and rules never raise unhandled exceptions on arbitrary event input.

**7.4** Unit tests must cover the Detection_Engine handler: multiple rules firing, rule exception handling, zero findings case.

---

## Requirement 8: Documentation

**8.1** A `docs/detection-rules.md` file must document each rule: `rule_id`, `rule_name`, severity, confidence, trigger conditions, and example event.

**8.2** The existing `docs/detections/detection-rules.md` stub must be updated or replaced.
