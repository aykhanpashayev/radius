# Design Document — Phase 6: Testing and Documentation

## Overview

Phase 6 brings Radius to production quality through two parallel workstreams: a comprehensive integration test suite and a complete documentation refresh. No Lambda handlers, DynamoDB table definitions, API contracts, or Terraform module interfaces are modified — all work is purely additive.

The integration test suite validates the full event processing pipeline end-to-end using moto for in-process AWS mocking. Tests are organised in `backend/tests/integration/` and cover five attack scenarios, all five DynamoDB tables, and the complete normalizer → detection_engine → incident_processor → score_engine pipeline.

The documentation workstream updates six existing doc files and creates two new ones, bringing all content in line with the Phase 3–5 implementations.

---

## Architecture

### Integration Test Architecture

```
pytest backend/tests/integration/
        │
        ├── conftest.py          ← shared fixtures (moto context, table setup)
        │       │
        │       ├── aws_credentials fixture   (fake env vars, no live AWS)
        │       ├── dynamodb_tables fixture   (creates all 5 tables via moto)
        │       └── sns_topic fixture         (creates mocked Alert_Topic)
        │
        ├── test_pipeline_e2e.py         ← normalizer → DynamoDB write verification
        ├── test_detection_integration.py ← detection rule accuracy on real event shapes
        ├── test_scoring_integration.py   ← score engine + DynamoDB write verification
        ├── test_attack_scenarios.py      ← 5 attack scenario simulations
        └── test_incident_processor.py   ← incident lifecycle + SNS alert routing
```

Each test module imports real production code directly — no Lambda handler invocations across process boundaries. The pipeline is exercised by calling the normalizer, collector, detection engine, incident processor, and score engine functions directly with mocked DynamoDB and SNS clients provided by moto.

### Mocking Strategy

moto is used in decorator mode (`@mock_aws`) applied at the fixture level via `autouse=True`. This ensures every test function runs inside a fresh moto context with no state leakage between tests.

```
@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    # Set fake credentials so boto3 never attempts live AWS calls
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

@pytest.fixture
def dynamodb_tables(aws_credentials):
    with mock_aws():
        _create_all_tables()
        yield _table_names()
```

The `mock_aws()` context manager from moto intercepts all boto3 calls to DynamoDB, Lambda, and SNS. No live credentials or environment variables are required.

### DynamoDB Table Setup

The `conftest.py` fixture creates all five tables with their exact primary key and GSI definitions matching `infra/modules/dynamodb/main.tf`:

| Table | PK | SK | GSIs |
|---|---|---|---|
| Identity_Profile | `identity_arn` | — | IdentityTypeIndex, AccountIndex |
| Blast_Radius_Score | `identity_arn` | — | ScoreRangeIndex, SeverityIndex |
| Incident | `incident_id` | — | StatusIndex, SeverityIndex, IdentityIndex |
| Event_Summary | `identity_arn` | `timestamp` | EventIdIndex, EventTypeIndex, TimeRangeIndex |
| Trust_Relationship | `source_arn` | `target_arn` | RelationshipTypeIndex, TargetAccountIndex |

The `IdentityIndex` GSI on the Incident table uses `KEYS_ONLY` projection — this must be replicated exactly in the fixture or `find_duplicate()` in `processor.py` will fail.

### Test Directory Structure

```
backend/tests/
├── (existing unit tests — unchanged)
├── test_detection_context.py
├── test_detection_engine.py
├── test_detection_properties.py
├── test_detection_rules.py
├── test_rule_engine.py
├── test_score_engine_properties.py
├── test_scoring_context.py
├── test_scoring_rules.py
└── integration/
    ├── __init__.py
    ├── conftest.py
    ├── test_pipeline_e2e.py
    ├── test_detection_integration.py
    ├── test_scoring_integration.py
    ├── test_attack_scenarios.py
    └── test_incident_processor.py
```

---

## Components and Interfaces

### conftest.py — Shared Fixtures

```python
# Key fixtures provided to all integration tests

aws_credentials(monkeypatch)        # autouse — sets fake boto3 env vars
dynamodb_tables(aws_credentials)    # yields dict of table names inside mock_aws()
sns_topic(dynamodb_tables)          # creates mocked SNS Alert_Topic, yields ARN
table_names()                       # returns the standard table name dict used by handlers
```

The `dynamodb_tables` fixture yields a dict:
```python
{
    "identity_profile": "test-identity-profile",
    "blast_radius_score": "test-blast-radius-score",
    "incident": "test-incident",
    "event_summary": "test-event-summary",
    "trust_relationship": "test-trust-relationship",
}
```

### Pipeline Invocation Pattern

Integration tests do not invoke Lambda handlers via HTTP or subprocess. Instead they call the underlying business logic functions directly, patching only the environment variables that handlers read at module level:

```python
# Pattern used across all integration test modules
def _run_normalizer(raw_event, tables, monkeypatch):
    monkeypatch.setenv("EVENT_SUMMARY_TABLE", tables["event_summary"])
    event_summary = parse_cloudtrail_event(raw_event)
    put_item(tables["event_summary"], event_summary)
    return event_summary

def _run_collector(event_summary, raw_event, tables):
    upsert_identity_profile(tables["identity_profile"], event_summary["identity_arn"], event_summary)
    if event_summary["event_type"].endswith("AssumeRole"):
        record_trust_relationship(tables["trust_relationship"], event_summary, raw_event.get("detail", raw_event))
    return event_summary

def _run_detection(event_summary, tables):
    ctx = DetectionContext.build(
        identity_arn=event_summary["identity_arn"],
        current_event_id=event_summary["event_id"],
        current_event_timestamp=event_summary["timestamp"],
        event_summary_table=tables["event_summary"],
    )
    engine = RuleEngine()
    return engine.evaluate(event_summary, ctx)

def _run_incident_processor(finding, tables, sns_topic_arn):
    validate_finding(asdict(finding))
    duplicate = find_duplicate(tables["incident"], finding.identity_arn, finding.detection_type)
    if duplicate:
        append_event_to_incident(tables["incident"], duplicate["incident_id"], finding.related_event_ids)
        return duplicate, False  # (incident, is_new)
    incident = create_incident(tables["incident"], asdict(finding))
    publish_alert(sns_topic_arn, incident)
    return incident, True

def _run_score_engine(identity_arn, tables):
    ctx = ScoringContext.build(identity_arn, tables)
    engine = RuleEngine()  # score_engine RuleEngine
    result = engine.evaluate(ctx)
    _write_score(result, tables["blast_radius_score"])
    return result
```

### End-to-End Pipeline Sequence

```
raw_cloudtrail_event
        │
        ▼
parse_cloudtrail_event()          → event_summary dict
        │
        ├──► put_item(Event_Summary table)
        │
        ├──► upsert_identity_profile()    → Identity_Profile table
        │
        ├──► record_trust_relationship()  → Trust_Relationship table (AssumeRole only)
        │
        ├──► DetectionContext.build()     → queries Event_Summary table
        │         │
        │         ▼
        │    RuleEngine.evaluate()        → list[Finding]
        │         │
        │         ▼
        │    create_incident() / append_event_to_incident()  → Incident table
        │    publish_alert()              → SNS Alert_Topic
        │
        └──► ScoringContext.build()       → queries all 4 tables
                  │
                  ▼
             RuleEngine.evaluate()        → ScoreResult
                  │
                  ▼
             put_item(Blast_Radius_Score table)
```

---

## Data Models

### CloudTrail Event Fixture Shape

Integration tests use two categories of event fixtures:

**1. File-based fixtures** — loaded from `sample-data/cloud-trail-events/`:
- `suspicious-privilege-escalation.json` — AttachUserPolicy for a newly created user
- `suspicious-cross-account-access.json` — AssumeRole targeting account 987654321098
- `sts-assume-role.json` — standard cross-account AssumeRole
- `iam-create-user.json` — benign user creation
- `iam-attach-policy.json` — policy attachment

**2. Programmatically constructed fixtures** — built inline for attack scenarios requiring sequences of events or specific timing:

```python
def _make_cloudtrail_event(event_name, identity_arn, account_id, event_time=None, extra_params=None):
    """Minimal valid CloudTrail event dict for integration testing."""
    return {
        "detail": {
            "eventVersion": "1.08",
            "userIdentity": {
                "type": "IAMUser",
                "arn": identity_arn,
                "accountId": account_id,
            },
            "eventTime": event_time or datetime.now(timezone.utc).isoformat(),
            "eventSource": f"{event_name.split(':')[0]}.amazonaws.com",
            "eventName": event_name.split(":")[-1],
            "awsRegion": "us-east-1",
            "sourceIPAddress": "203.0.113.1",
            "userAgent": "aws-cli/2.15.0",
            "requestParameters": extra_params or {},
            "responseElements": None,
            "eventID": str(uuid.uuid4()),
            "eventType": "AwsApiCall",
            "managementEvent": True,
            "recipientAccountId": account_id,
        }
    }
```

### Attack Scenario Event Sequences

Each scenario is a sequence of `_make_cloudtrail_event()` calls processed through the full pipeline:

**Scenario 1 — Privilege Escalation**
```
T+0m:  iam:CreateUser    (identity: attacker, account: 111111111111)
T+5m:  iam:AttachUserPolicy  (identity: attacker, account: 111111111111)
         → triggers privilege_escalation rule (CreateUser in recent_events_60m)
         → Incident created: detection_type=privilege_escalation
```

**Scenario 2 — Cross-Account Lateral Movement**
```
T+0m:  sts:AssumeRole    (identity: dev-user@111111111111, roleArn: role@987654321098)
         → triggers cross_account_role_assumption rule
         → Incident created: detection_type=cross_account_role_assumption
```

**Scenario 3 — Logging Disruption**
```
T+0m:  cloudtrail:StopLogging  (identity: attacker, account: 111111111111)
         → triggers logging_disruption rule (severity: Critical)
         → Incident created: severity=Critical
```

**Scenario 4 — API Burst**
```
T+0m to T+4m:  20x ec2:DescribeInstances  (identity: attacker, account: 111111111111)
                 → all 20 events written to Event_Summary
                 → DetectionContext.recent_events_5m has 20 events
                 → triggers api_burst_anomaly rule
                 → Incident created: detection_type=api_burst_anomaly
```

**Scenario 5 — Root User Activity**
```
T+0m:  iam:CreateUser  (identity: arn:aws:iam::111111111111:root, identity_type: Root)
         → triggers root_user_activity rule (severity: Very High)
         → Incident created: detection_type=root_user_activity
```

**Scenario 6 — Deduplication**
```
T+0m:  cloudtrail:StopLogging  → Incident A created (incident_id: uuid-A)
T+1h:  cloudtrail:StopLogging  → find_duplicate() finds Incident A → append_event_to_incident()
         → DynamoDB scan: exactly 1 Incident record for this identity+detection_type
```

### DynamoDB Record Shapes (Expected by Tests)

**Event_Summary** (written by normalizer):
```python
{
    "identity_arn": str,       # PK
    "timestamp": str,          # SK — ISO 8601 UTC
    "event_id": str,
    "event_type": str,         # e.g. "iam:AttachUserPolicy"
    "date_partition": str,     # YYYY-MM-DD
    "source_ip": str,
    "user_agent": str,
    "event_parameters": dict,
    "account_id": str,
    "region": str,
    "ttl": int,                # Unix epoch, ~90 days from now
}
```

**Identity_Profile** (written by collector):
```python
{
    "identity_arn": str,       # PK
    "identity_type": str,      # IAMUser | AssumedRole | AWSService
    "account_id": str,
    "last_activity_timestamp": str,
    "creation_date": str,
    "is_active": bool,
    "activity_count": int,
    "tags": dict,
}
```

**Trust_Relationship** (written by collector on AssumeRole):
```python
{
    "source_arn": str,         # PK
    "target_arn": str,         # SK
    "relationship_type": str,  # CrossAccount | AssumeRole
    "source_account_id": str,
    "target_account_id": str,
    "discovery_timestamp": str,
    "is_active": bool,
    "last_used_timestamp": str,
}
```

**Incident** (written by incident_processor):
```python
{
    "incident_id": str,        # PK — UUID v4
    "identity_arn": str,
    "detection_type": str,
    "severity": str,
    "confidence": int,
    "status": str,             # initial: "open"
    "creation_timestamp": str,
    "update_timestamp": str,
    "related_event_ids": list,
    "status_history": list,    # initial: [{"status": "open", "timestamp": ...}]
    "notes": str,
    "assigned_to": str,
}
```

**Blast_Radius_Score** (written by score_engine):
```python
{
    "identity_arn": str,       # PK
    "score_value": int,        # 0–100
    "severity_level": str,     # Low | Moderate | High | Very High | Critical
    "calculation_timestamp": str,
    "contributing_factors": list,
}
```

---

## Documentation Update Strategy

### Files to Update (existing content, needs refresh)

| File | Status | Changes needed |
|---|---|---|
| `docs/architecture.md` | Exists — partially stale | Add Score_Engine to pipeline diagram; add all 5 DynamoDB tables; add all 6 Lambda functions with triggers; add Terraform module dependency section |
| `docs/deployment.md` | Exists — mostly current | Add Python version requirement; document `verify-deployment.sh` checks; add 3 troubleshooting scenarios; document dev vs prod differences more explicitly |
| `docs/scoring-model.md` | Exists — complete | Minor: verify all 8 rules are documented; confirm worked example matches current rule implementations |
| `docs/detection-rules.md` | Exists — complete | Minor: verify all 7 rules documented; confirm deduplication section is accurate |
| `docs/database-schema.md` | Exists — complete | Minor: add `ttl` field to Event_Summary; add `source_account_id`/`target_account_id` to Trust_Relationship |

### Files to Create (net-new)

| File | Purpose |
|---|---|
| `docs/dashboard.md` | Dashboard usage guide — all pages, filtering, incident status transitions, score display, local dev setup, production deployment |
| `docs/developer-guide.md` | Contributor guide — adding detection rules, adding scoring rules, test structure, running tests, injecting events, Lambda packaging |

### Documentation Scope Decisions

- `docs/scoring-model.md` and `docs/detection-rules.md` are already comprehensive from Phases 3–4. They need verification passes, not rewrites.
- `docs/architecture.md` needs the most work — it still references Detection_Engine and Score_Engine as "PLACEHOLDER" from Phase 2.
- `docs/dashboard.md` is entirely new — `docs/frontend.md` covers deployment but not usage.
- `docs/developer-guide.md` is entirely new — no contributor guide exists.

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Event_Summary Write Round-Trip

*For any* valid CloudTrail event, parsing and writing it through the normalizer should produce an Event_Summary record in DynamoDB that contains all required fields (`identity_arn`, `timestamp`, `event_id`, `event_type`, `date_partition`, `account_id`) and a `ttl` value within 60 seconds of `now + 90 days`.

**Validates: Requirements 2.1, 7.1, 7.6**

### Property 2: Identity_Profile Upsert Round-Trip

*For any* valid CloudTrail event, processing it through Identity_Collector should create or update an Identity_Profile record in DynamoDB containing `identity_arn`, `identity_type`, `account_id`, and `last_activity_timestamp`.

**Validates: Requirements 2.2, 7.2**

### Property 3: Trust_Relationship Write Round-Trip

*For any* AssumeRole-family event (`AssumeRole`, `AssumeRoleWithSAML`, `AssumeRoleWithWebIdentity`) with a valid `roleArn` in `requestParameters`, processing it through Identity_Collector should write a Trust_Relationship record containing `source_arn`, `target_arn`, `relationship_type`, `source_account_id`, and `target_account_id`.

**Validates: Requirements 2.3, 7.3**

### Property 4: Invalid Event Rejection

*For any* CloudTrail event missing one or more required fields (`eventName`, `userIdentity`, `eventTime`), Event_Normalizer should return a non-ok status and write zero records to any DynamoDB table.

**Validates: Requirements 2.6**

### Property 5: Detection Finding Validity

*For any* event and DetectionContext pair that causes any detection rule to produce a Finding, the Finding's `detection_type` must equal the rule's `rule_id` and `confidence` must be an integer in the range 0 to 100 inclusive.

**Validates: Requirements 3.6, 3.7**

### Property 6: Score Write Round-Trip

*For any* identity with a valid ScoringContext, Score_Engine should write a Blast_Radius_Score record to DynamoDB where `score_value` is in the range 0 to 100 inclusive and `severity_level` is the correct classification for that `score_value` according to the documented thresholds (0–19 Low, 20–39 Moderate, 40–59 High, 60–79 Very High, 80–100 Critical).

**Validates: Requirements 4.5, 4.6, 4.7, 7.4**

### Property 7: Incident Structure Invariant

*For any* valid Finding passed to Incident_Processor, the resulting Incident record must contain all required fields (`incident_id`, `identity_arn`, `detection_type`, `severity`, `confidence`, `status`, `creation_timestamp`, `update_timestamp`, `related_event_ids`, `status_history`), have `incident_id` matching the UUID v4 format, have initial `status` equal to `"open"`, and have `status_history` containing exactly one entry.

**Validates: Requirements 6.1, 6.2, 6.3, 7.5**

### Property 8: Deduplication Invariant

*For any* `(identity_arn, detection_type)` pair, if Incident_Processor receives two Findings with the same pair within a 24-hour window, exactly one Incident record should exist in DynamoDB for that pair (the second invocation appends to `related_event_ids` rather than creating a new record).

**Validates: Requirements 5.6, 6.4**

### Property 9: SNS Alert Routing

*For any* Finding, Incident_Processor should publish an SNS alert to the Alert_Topic if and only if the Finding's `severity` is one of `High`, `Very High`, or `Critical`. Findings with severity `Low` or `Moderate` must not produce any SNS publish call.

**Validates: Requirements 6.5, 6.6**

---

## Error Handling

### Moto Limitations

- moto does not enforce DynamoDB GSI projection types at query time — tests that rely on `KEYS_ONLY` projections returning only keys must be written to not assert on projected attributes.
- moto's SNS `list_subscriptions` and message inspection require using `boto3.client("sns").get_queue_attributes()` via an SQS subscription, or reading from `moto`'s internal message store via `sns.list_messages()` (available in newer moto versions). The design uses an SQS queue subscribed to the SNS topic for SNS message assertion.
- The `IdentityIndex` GSI on the Incident table uses `KEYS_ONLY` projection. The `find_duplicate()` function in `processor.py` queries this GSI and filters by `detection_type` and `status` using a `FilterExpression`. moto supports this correctly.

### Test Isolation Failures

If a test fails mid-execution and leaves DynamoDB state, subsequent tests in the same session could be affected. The `mock_aws()` context manager in the fixture teardown path handles this — even on exception, the context manager exits and destroys all mocked state. This is enforced by using `yield` inside the `with mock_aws():` block.

### TTL Field Verification

The `ttl` field on Event_Summary records is a Unix epoch integer. The normalizer currently writes `event_summary` without a `ttl` field (the field is set by the handler, not `parse_cloudtrail_event`). Integration tests that verify `ttl` must call the handler-level logic or explicitly set the TTL after normalization, matching what the production handler does.

### API Burst Scenario Timing

The `api_burst_anomaly` rule uses `DetectionContext.recent_events_5m`, which is derived in-memory by filtering `recent_events_60m` against `datetime.now(timezone.utc) - timedelta(minutes=5)`. Integration tests that simulate the API burst scenario must write all 20 events with timestamps within the last 5 minutes (not mocked time) to ensure the in-memory filter includes them. Using `datetime.now(timezone.utc)` at event construction time is sufficient.

---

## Testing Strategy

### Dual Testing Approach

Phase 6 uses both unit tests and property-based tests, which are complementary:

- **Unit tests** (existing, `backend/tests/`): verify specific examples, edge cases, and rule-level correctness. These are fast and deterministic.
- **Property-based tests** (existing + new, using Hypothesis): verify universal properties across many generated inputs. These catch edge cases that example tests miss.
- **Integration tests** (new, `backend/tests/integration/`): verify that components work correctly together with real DynamoDB interactions via moto. These validate the pipeline as a whole.

### Unit Testing Balance

Integration tests focus on:
- Pipeline composition (normalizer → collector → detection → incident → scoring)
- DynamoDB write correctness (field presence, types, values)
- Attack scenario end-to-end flows
- Deduplication behaviour across the full stack

Integration tests do not duplicate:
- Rule-level logic (covered by `test_detection_rules.py`, `test_scoring_rules.py`)
- Property-based correctness (covered by `test_detection_properties.py`, `test_score_engine_properties.py`)
- Engine orchestration (covered by `test_detection_engine.py`, `test_rule_engine.py`)

### Property-Based Test Configuration

Property-based tests use [Hypothesis](https://hypothesis.readthedocs.io/). Each property test runs a minimum of 100 iterations.

Each property test must be tagged with a comment referencing the design property it validates:

```python
# Feature: phase-6-testing-and-documentation, Property 1: Event_Summary write round-trip
@given(raw_event=valid_cloudtrail_event_strategy())
@settings(max_examples=100)
def test_event_summary_write_round_trip(raw_event, dynamodb_tables):
    ...
```

Tag format: `Feature: {feature_name}, Property {number}: {property_text}`

Each correctness property defined above must be implemented by exactly one property-based test. The mapping is:

| Property | Test function | File |
|---|---|---|
| P1: Event_Summary write round-trip | `test_event_summary_write_round_trip` | `test_pipeline_e2e.py` |
| P2: Identity_Profile upsert round-trip | `test_identity_profile_upsert_round_trip` | `test_pipeline_e2e.py` |
| P3: Trust_Relationship write round-trip | `test_trust_relationship_write_round_trip` | `test_pipeline_e2e.py` |
| P4: Invalid event rejection | `test_invalid_event_rejected` | `test_pipeline_e2e.py` |
| P5: Detection finding validity | `test_detection_finding_validity` | `test_detection_integration.py` |
| P6: Score write round-trip | `test_score_write_round_trip` | `test_scoring_integration.py` |
| P7: Incident structure invariant | `test_incident_structure_invariant` | `test_incident_processor.py` |
| P8: Deduplication invariant | `test_deduplication_invariant` | `test_incident_processor.py` |
| P9: SNS alert routing | `test_sns_alert_routing` | `test_incident_processor.py` |

### Hypothesis Strategies for Integration Tests

```python
# Strategy for generating valid CloudTrail events (used in P1, P2, P3, P4)
@st.composite
def valid_cloudtrail_event_strategy(draw):
    identity_arn = draw(st.from_regex(
        r"arn:aws:iam::[0-9]{12}:(user|role)/[a-zA-Z0-9_+=,.@/-]{1,32}",
        fullmatch=True,
    ))
    account_id = identity_arn.split(":")[4]
    event_name = draw(st.sampled_from([
        "CreateUser", "AttachUserPolicy", "PutRolePolicy",
        "AssumeRole", "StopLogging", "RunInstances", "ListUsers",
    ]))
    return _make_cloudtrail_event(event_name, identity_arn, account_id)

# Strategy for generating valid Findings (used in P7, P8, P9)
@st.composite
def valid_finding_strategy(draw):
    severity = draw(st.sampled_from(["Low", "Moderate", "High", "Very High", "Critical"]))
    return Finding(
        identity_arn=draw(st.from_regex(
            r"arn:aws:iam::[0-9]{12}:(user|role)/[a-zA-Z0-9_+=,.@/-]{1,32}",
            fullmatch=True,
        )),
        detection_type=draw(st.sampled_from([
            "privilege_escalation", "cross_account_role_assumption",
            "logging_disruption", "root_user_activity", "api_burst_anomaly",
            "iam_policy_modification_spike", "unusual_service_usage",
        ])),
        severity=severity,
        confidence=draw(st.integers(min_value=0, max_value=100)),
        related_event_ids=[draw(st.uuids().map(str))],
        description="Generated finding",
    )
```

### Running the Test Suite

```bash
# Run all integration tests
pytest backend/tests/integration/ -v

# Run only attack scenario tests
pytest backend/tests/integration/test_attack_scenarios.py -v

# Run full test suite (unit + property + integration)
pytest backend/tests/ -v

# Run with coverage
pytest backend/tests/ --cov=backend/functions --cov-report=term-missing
```

No live AWS environment variables are required. The `aws_credentials` fixture sets fake values that satisfy boto3's credential resolution without making any real API calls.
