# Developer Guide

This guide covers how to extend Radius with new detection and scoring rules, how the test suite is structured, and how to run tests, inject sample events, and package Lambda functions for deployment.

---

## Adding a New Detection Rule

Detection rules live in `backend/functions/detection_engine/rules/`. There are two rule types — choose based on whether your rule needs historical context.

### Step 1 — Choose the right interface

| Interface | Use when |
|---|---|
| `DetectionRule` | Rule fires on a single event with no DynamoDB reads |
| `ContextAwareDetectionRule` | Rule needs `recent_events_60m`, `recent_events_5m`, or `prior_services_30d` |

Both interfaces are defined in `backend/functions/detection_engine/interfaces.py`.

### Step 2 — Create the rule file

**Single-event rule** (`backend/functions/detection_engine/rules/my_rule.py`):

```python
from backend.functions.detection_engine.interfaces import DetectionRule, Finding
from backend.common.aws_utils import extract_event_name

class MyRule(DetectionRule):
    rule_id = "my_rule"
    rule_name = "MyRule"
    severity = "High"       # Low | Moderate | High | Very High | Critical
    confidence = 75         # 0–100

    def evaluate(self, event_summary: dict) -> Finding | None:
        event_name = extract_event_name(event_summary.get("event_type", ""))
        if event_name == "SomeDangerousAction":
            return Finding(
                identity_arn=event_summary.get("identity_arn", ""),
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description=f"Detected {event_name}",
            )
        return None
```

**Context-aware rule** (`backend/functions/detection_engine/rules/my_context_rule.py`):

```python
from backend.functions.detection_engine.interfaces import ContextAwareDetectionRule, Finding

class MyContextRule(ContextAwareDetectionRule):
    rule_id = "my_context_rule"
    rule_name = "MyContextRule"
    severity = "Moderate"
    confidence = 65

    def evaluate_with_context(self, event_summary: dict, context) -> Finding | None:
        if len(context.recent_events_60m) > 10:
            return Finding(
                identity_arn=event_summary.get("identity_arn", ""),
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description="High event volume in last 60 minutes",
            )
        return None
```

### Step 3 — Register the rule

Add an import and entry to `ALL_RULES` in `backend/functions/detection_engine/rules/__init__.py`:

```python
from backend.functions.detection_engine.rules.my_rule import MyRule

ALL_RULES = [
    ...,
    MyRule,
]
```

The `RuleEngine` instantiates every class in `ALL_RULES` at startup and evaluates them in order.

### Step 4 — Add unit tests

Create `backend/tests/test_my_rule.py`. At minimum, test:
- A triggering event returns a `Finding` with the correct `detection_type`, `severity`, and `confidence`
- A non-triggering event returns `None`

---

## Adding a New Scoring Rule

Scoring rules live in `backend/functions/score_engine/rules/`. All rules implement `ScoringRule` from `backend/functions/score_engine/interfaces.py`.

### Step 1 — Create the rule file

```python
from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_event_name

class MyScoreRule(ScoringRule):
    rule_id = "my_score_rule"
    rule_name = "MyScoreRule"
    max_contribution = 15

    def calculate(self, identity_arn: str, context) -> int:
        # context.events is a list of Event_Summary dicts
        count = sum(
            1 for e in context.events
            if extract_event_name(e.get("event_type", "")) == "SomeAction"
        )
        if count == 0:
            return 0
        if count <= 2:
            return 8
        return min(15, count * 5)
```

Rules must:
- Return an integer in `[0, max_contribution]`
- Never write to DynamoDB — `context` is read-only
- Be deterministic — same input always produces the same output

### Step 2 — Register the rule

Add to `backend/functions/score_engine/rules/__init__.py`:

```python
_try_import("backend.functions.score_engine.rules.my_score_rule", "MyScoreRule")
```

The `_try_import` helper loads rules defensively so a broken import doesn't crash the engine.

### Step 3 — Add unit tests

Create `backend/tests/test_my_score_rule.py`. Test:
- Each scoring tier returns the expected point value
- `calculate()` never exceeds `max_contribution`
- An empty context returns 0

---

## Test Structure

```
backend/tests/
├── conftest.py                     # shared pytest fixtures (unit tests)
├── test_rule_engine.py             # RuleEngine orchestration
├── test_scoring_rules.py           # scoring rule unit tests
├── test_scoring_context.py         # ScoringContext.build() unit tests
├── test_score_engine_properties.py # Hypothesis property tests for scoring
├── test_detection_rules.py         # detection rule unit tests
├── test_detection_engine.py        # detection engine orchestration
├── test_detection_context.py       # DetectionContext.build() unit tests
├── test_detection_properties.py    # Hypothesis property tests for detection
└── integration/
    ├── conftest.py                 # moto fixtures (mocked AWS)
    ├── test_pipeline_e2e.py        # normalizer → DynamoDB round-trips
    ├── test_detection_integration.py
    ├── test_scoring_integration.py
    ├── test_attack_scenarios.py    # full 5-scenario attack simulations
    └── test_incident_processor.py  # incident lifecycle + SNS routing
```

Unit tests in `backend/tests/` use no AWS mocking — they call business logic functions directly with plain Python dicts.

Integration tests in `backend/tests/integration/` use [moto](https://docs.getmoto.org/) to mock DynamoDB and SNS. All mocking is applied at the fixture level via `autouse=True` — no per-test `@mock_aws` decorators.

---

## Running Tests

### Full test suite

```bash
pytest backend/tests/ -v
```

### Unit tests only

```bash
pytest backend/tests/ -v --ignore=backend/tests/integration
```

### Integration tests only

```bash
pytest backend/tests/integration/ -v
```

### With coverage

```bash
pytest backend/tests/ --cov=backend/functions --cov-report=term-missing
```

### Single test file

```bash
pytest backend/tests/test_detection_rules.py -v
```

### Property-based tests (Hypothesis)

Property tests run as part of the normal suite. To run with more examples:

```bash
pytest backend/tests/test_score_engine_properties.py -v --hypothesis-seed=0
```

---

## Injecting Sample Events

`scripts/inject-events.py` sends CloudTrail events to EventBridge to trigger the full pipeline in a deployed dev environment.

```bash
# Inject all events in the sample-data directory
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events

# Inject a single event file
python scripts/inject-events.py --env dev --file sample-data/cloud-trail-events/sts-assume-role.json

# Validate events without sending to AWS
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events --dry-run

# Target a specific region
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events --region eu-west-1
```

Events are sent in batches of 10 (EventBridge `PutEvents` limit). The script validates each file before sending — events missing `eventName`, `userIdentity`, or `eventTime` are skipped with an error message.

---

## Lambda Packaging and Deployment

### Build all Lambda packages

```bash
./scripts/build-lambdas.sh --env dev --bucket my-artifact-bucket --region us-east-1
```

If `lambda_s3_bucket` is set in `infra/envs/dev/terraform.tfvars`, the `--bucket` flag can be omitted:

```bash
./scripts/build-lambdas.sh --env dev
```

The script:
1. Installs Python dependencies from each function's `requirements.txt` into a build directory
2. Copies `backend/common/` shared utilities into each package
3. Zips the package (excluding `*.pyc` and `__pycache__`)
4. Uploads to `s3://<bucket>/functions/<function_name>.zip`

### Deploy infrastructure

```bash
./scripts/deploy-infra.sh --env dev
```

Terraform reads the S3 zip paths and updates Lambda function code if the S3 ETag changed. Always run `build-lambdas.sh` before `deploy-infra.sh` when deploying code changes.

See `docs/deployment.md` for the full deployment workflow including first-time setup and rollback.
