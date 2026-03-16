# Phase 4 Design: Detection Rules and Incident Logic

## Overview

Phase 4 replaces the Detection_Engine placeholder with a real rule-based detection engine. The design mirrors the Phase 3 Score_Engine architecture: a `DetectionContext` data fetcher, a `RuleEngine` orchestrator, and 7 concrete `DetectionRule` implementations. All changes are additive — existing infrastructure, tables, and APIs are unchanged.

---

## Architecture

```
EventBridge (CloudTrail events)
    │
    ▼
Event_Normalizer
    ├── writes Event_Summary (DynamoDB)
    ├── invokes Identity_Collector (async)
    ├── invokes Score_Engine (async)          ← Phase 3
    └── invokes Detection_Engine (async)      ← Phase 4 (existing invocation, new logic)
            │
            ▼
    DetectionContext.build()
    (reads Event_Summary for historical context)
            │
            ▼
    RuleEngine.evaluate(event_summary, context)
    (evaluates all 7 rules)
            │
            ├── Finding 1 → Incident_Processor (async invoke)
            ├── Finding 2 → Incident_Processor (async invoke)
            └── ...
                    │
                    ▼
            Incident_Processor
            (deduplication, create_incident, SNS alert)
                    │
                    ▼
            Incident table (DynamoDB)
```

---

## Component Design

### DetectionContext

```python
@dataclass
class DetectionContext:
    identity_arn: str
    recent_events_60m: list[dict]   # events in last 60 minutes (includes current event window)
    prior_services_30d: set[str]    # distinct services used BEFORE the current event timestamp

    @property
    def recent_events_5m(self) -> list[dict]:
        """Derived in-memory from recent_events_60m — no extra DynamoDB query."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        return [e for e in self.recent_events_60m if e.get("timestamp", "") >= cutoff]

    @classmethod
    def build(cls, identity_arn: str, current_event_id: str,
              current_event_timestamp: str, event_summary_table: str) -> "DetectionContext":
        ...
```

`build()` performs **two** DynamoDB queries against `Event_Summary`:

1. **60-minute query**: `timestamp >= now - 60m` — used directly for IAMPolicyModificationSpike; `recent_events_5m` is derived in-memory from this set (no third query).
2. **30-day query**: `timestamp >= now - 30d AND timestamp < current_event_timestamp` — events strictly **before** the current event. The current event's `event_id` is also excluded as a safety guard. Service prefixes are extracted into `prior_services_30d`.

The `prior_services_30d` field intentionally excludes the current event so that UnusualServiceUsage correctly detects a service being used for the first time — if the current event were included, the rule would never fire for a genuinely new service.

Only context-aware rules (PrivilegeEscalation, IAMPolicyModificationSpike, APIBurstAnomaly, UnusualServiceUsage) use `DetectionContext`. Single-event rules (CrossAccountRoleAssumption, LoggingDisruption, RootUserActivity) operate on the Event_Summary dict only.

---

### DetectionRule Interface (extended from Phase 2)

```python
class DetectionRule(ABC):
    rule_id: str
    rule_name: str
    severity: str

    @abstractmethod
    def evaluate(self, event_summary: dict) -> Finding | None:
        """Evaluate a single event. No DynamoDB calls allowed."""

class ContextAwareDetectionRule(DetectionRule):
    @abstractmethod
    def evaluate_with_context(
        self, event_summary: dict, context: DetectionContext
    ) -> Finding | None:
        """Evaluate with pre-fetched historical context."""
```

Two rule types:
- `DetectionRule` — single-event rules: CrossAccountRoleAssumption, LoggingDisruption, RootUserActivity
- `ContextAwareDetectionRule` — rules needing historical data: PrivilegeEscalation, IAMPolicyModificationSpike, APIBurstAnomaly, UnusualServiceUsage

All rules use `extract_event_name(event_summary["event_type"])` from `backend/common/aws_utils.py` — never raw string splitting inline. This is enforced consistently across all 7 rules.

---

### RuleEngine

```python
class RuleEngine:
    def __init__(self):
        self.rules: list[DetectionRule] = [rule() for rule in ALL_RULES]

    def evaluate(
        self,
        event_summary: dict,
        context: DetectionContext,
    ) -> list[Finding]:
        findings = []
        for rule in self.rules:
            try:
                if isinstance(rule, ContextAwareDetectionRule):
                    finding = rule.evaluate_with_context(event_summary, context)
                else:
                    finding = rule.evaluate(event_summary)
                if finding is not None:
                    findings.append(finding)
            except Exception:
                logger.warning("Rule evaluation failed", ...)
        return findings
```

---

### Detection_Engine Handler

```python
# Module-level (warm-start reuse)
_engine = RuleEngine()
_EVENT_SUMMARY_TABLE = os.environ["EVENT_SUMMARY_TABLE"]
_INCIDENT_PROCESSOR_ARN = os.environ["INCIDENT_PROCESSOR_ARN"]

def lambda_handler(event, context):
    identity_arn = event.get("identity_arn", "unknown")
    
    # Build context for context-aware rules
    det_context = DetectionContext.build(identity_arn, _EVENT_SUMMARY_TABLE)
    
    # Evaluate all rules
    findings = _engine.evaluate(event, det_context)
    
    # Forward each finding to Incident_Processor
    forwarded, failures = 0, 0
    for finding in findings:
        try:
            _lambda_client.invoke(
                FunctionName=_INCIDENT_PROCESSOR_ARN,
                InvocationType="Event",
                Payload=json.dumps(asdict(finding), default=str),
            )
            forwarded += 1
        except Exception:
            failures += 1
    
    return {"status": "ok", "findings": forwarded, "failures": failures}
```

---

## Detection Rules

### Rule 1 — PrivilegeEscalation

| Attribute | Value |
|-----------|-------|
| `rule_id` | `privilege_escalation` |
| `rule_name` | `PrivilegeEscalation` |
| `severity` | High |
| `confidence` | 80 |
| Type | Context-aware |

Moved to context-aware because the combined `CreateUser` + `AttachUserPolicy` indicator requires checking recent prior events — making it a purely single-event rule would miss this pattern.

**Trigger logic:**

```python
DIRECT_ESCALATION_EVENTS = {"CreatePolicyVersion", "AddUserToGroup", "PassRole"}

event_name = extract_event_name(event_summary["event_type"])

# Direct single-event indicators
if event_name in DIRECT_ESCALATION_EVENTS:
    return Finding(description=f"Privilege escalation via {event_name}")

# Combined indicator: AttachUserPolicy following a recent CreateUser
if event_name == "AttachUserPolicy":
    recent_names = {
        extract_event_name(e["event_type"])
        for e in context.recent_events_60m
    }
    if "CreateUser" in recent_names:
        return Finding(description="Privilege escalation: CreateUser followed by AttachUserPolicy")

return None
```

---

### Rule 2 — IAMPolicyModificationSpike

| Attribute | Value |
|-----------|-------|
| `rule_id` | `iam_policy_modification_spike` |
| `rule_name` | `IAMPolicyModificationSpike` |
| `severity` | High |
| `confidence` | 75 |
| Type | Context-aware |

**Trigger logic:**

```python
mutation_count = sum(
    1 for e in context.recent_events_60m
    if extract_event_name(e["event_type"]) in IAM_MUTATION_EVENTS
)
if mutation_count >= 5:
    trigger → Finding(description=f"{mutation_count} IAM mutations in last 60 minutes")
```

---

### Rule 3 — CrossAccountRoleAssumption

| Attribute | Value |
|-----------|-------|
| `rule_id` | `cross_account_role_assumption` |
| `rule_name` | `CrossAccountRoleAssumption` |
| `severity` | Moderate |
| `confidence` | 70 |
| Type | Single-event |

**Trigger logic:**

```python
if extract_event_name(event_summary["event_type"]) == "AssumeRole":
    role_arn = event_summary.get("event_parameters", {}).get("roleArn", "")
    target_account = extract_account_id(role_arn)
    identity_account = extract_account_id(event_summary["identity_arn"])
    if target_account and target_account != identity_account:
        trigger → Finding(description=f"Cross-account AssumeRole from {identity_account} to {target_account}")
```

---

### Rule 4 — LoggingDisruption

| Attribute | Value |
|-----------|-------|
| `rule_id` | `logging_disruption` |
| `rule_name` | `LoggingDisruption` |
| `severity` | Critical |
| `confidence` | 95 |
| Type | Single-event |

**Trigger logic:**

```python
DISRUPTION_EVENTS = {
    "StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors",
    "DeleteFlowLogs", "DeleteLogGroup", "DeleteLogStream"
}
event_name = extract_event_name(event_summary["event_type"])
if event_name in DISRUPTION_EVENTS:
    trigger → Finding(description=f"Logging disruption via {event_name}")
```

---

### Rule 5 — RootUserActivity

| Attribute | Value |
|-----------|-------|
| `rule_id` | `root_user_activity` |
| `rule_name` | `RootUserActivity` |
| `severity` | Very High |
| `confidence` | 100 |
| Type | Single-event |

**Trigger logic:**

```python
# Primary check: explicit identity_type field
identity_type = event_summary.get("identity_type", "")
identity_arn = event_summary.get("identity_arn", "")

if identity_type == "Root":
    return Finding(description="Root account activity detected")

# Fallback: ARN-based detection for cases where identity_type is not set
if ":root" in identity_arn.lower():
    return Finding(description="Root account activity detected (ARN-based)")

return None
```

Primary check is `identity_type == "Root"`. ARN substring matching is a fallback only, guarding against cases where the normalizer does not populate `identity_type`.

---

### Rule 6 — APIBurstAnomaly

| Attribute | Value |
|-----------|-------|
| `rule_id` | `api_burst_anomaly` |
| `rule_name` | `APIBurstAnomaly` |
| `severity` | Moderate |
| `confidence` | 65 |
| Type | Context-aware |

**Trigger logic:**

```python
call_count = len(context.recent_events_5m)
if call_count >= 20:
    trigger → Finding(description=f"{call_count} API calls in last 5 minutes")
```

---

### Rule 7 — UnusualServiceUsage

| Attribute | Value |
|-----------|-------|
| `rule_id` | `unusual_service_usage` |
| `rule_name` | `UnusualServiceUsage` |
| `severity` | Low |
| `confidence` | 60 |
| Type | Context-aware |

**Trigger logic:**

```python
HIGH_RISK_SERVICES = {"sts", "iam", "organizations", "kms", "secretsmanager", "ssm"}

current_service = extract_event_name(event_summary.get("event_type", "").split(":")[0])
# More precisely: service is the prefix before ":"
current_service = event_summary.get("event_type", "").split(":")[0].lower()

if current_service in HIGH_RISK_SERVICES and current_service not in context.prior_services_30d:
    return Finding(description=f"First use of high-risk service '{current_service}' in 30 days")

return None
```

`context.prior_services_30d` contains services from events **before** the current event timestamp, so the current event's service is never pre-included. This ensures the rule correctly fires when a service is genuinely new.

---

## File Structure

```
backend/functions/detection_engine/
├── handler.py          ← rewritten (real logic, same interface)
├── interfaces.py       ← extended (ContextAwareDetectionRule, DetectionContext)
├── engine.py           ← new (RuleEngine)
├── context.py          ← new (DetectionContext)
├── requirements.txt    ← add hypothesis (test dep)
└── rules/
    ├── __init__.py                      ← exports ALL_RULES
    ├── privilege_escalation.py
    ├── iam_policy_modification_spike.py
    ├── cross_account_role_assumption.py
    ├── logging_disruption.py
    ├── root_user_activity.py
    ├── api_burst_anomaly.py
    └── unusual_service_usage.py

backend/tests/
├── test_detection_rules.py         ← unit tests for all 7 rules
├── test_detection_engine.py        ← unit tests for RuleEngine + handler
└── test_detection_properties.py    ← property-based tests
```

---

## Key Design Decisions

- **Mirror Phase 3 architecture** — `DetectionContext` mirrors `ScoringContext`; `RuleEngine` mirrors the scoring `RuleEngine`. This keeps the codebase consistent and the pattern familiar.
- **Two rule types** — single-event rules (CrossAccountRoleAssumption, LoggingDisruption, RootUserActivity) avoid DynamoDB reads entirely; context-aware rules (PrivilegeEscalation, IAMPolicyModificationSpike, APIBurstAnomaly, UnusualServiceUsage) receive pre-fetched data. This keeps rules testable without mocking DynamoDB.
- **PrivilegeEscalation is context-aware** — the combined `CreateUser` + `AttachUserPolicy` indicator requires checking recent prior events. Classifying it as single-event would miss this pattern.
- **Two DynamoDB queries, not three** — `DetectionContext.build()` performs one 60-minute query and one 30-day query. `recent_events_5m` is derived in-memory from the 60-minute result set. This avoids a redundant third query.
- **`prior_services_30d` excludes the current event** — the 30-day query uses `timestamp < current_event_timestamp` so the current event's service is never pre-included. This is what makes UnusualServiceUsage work correctly.
- **Consistent event name extraction** — all rules call `extract_event_name(event_summary["event_type"])` from `backend/common/aws_utils.py`. No inline string splitting in rule logic.
- **Root detection: `identity_type` first, ARN fallback second** — `identity_type == "Root"` is the primary check. ARN substring matching (`:root`) is a fallback only, avoiding false positives from identities with "root" in their name.
- **Static confidence per rule** — confidence values are rule-defined constants in Phase 4. Dynamic confidence tuning (based on historical false-positive rates, correlated signals, etc.) is deferred to a future phase.
- **No deduplication in Detection_Engine** — Incident_Processor already handles 24-hour deduplication by `identity_arn` + `detection_type`. Detection_Engine forwards all findings.
- **`rule_id` = `detection_type`** — the Finding's `detection_type` field is set to `rule.rule_id`, ensuring Incident_Processor deduplication keys, analytics filters, and rule traceability all stay aligned.
- **No new infrastructure** — Detection_Engine already has IAM permissions to read Event_Summary (via `ReadEventSummary` policy statement). No Terraform changes needed.

---

## Correctness Properties

1. **Finding validity** — every Finding has a non-empty `identity_arn`, `detection_type`, and valid `severity`
2. **Confidence bounds** — `0 <= confidence <= 100` for all findings
3. **Rule identity** — `finding.detection_type == rule.rule_id` for all rules
4. **No unhandled exceptions** — rules never propagate exceptions to the engine
5. **Determinism** — same event_summary + context always produces the same findings
6. **No false negatives on known triggers** — known trigger inputs always produce a Finding
7. **No false positives on empty input** — empty/minimal event_summary never triggers any rule
