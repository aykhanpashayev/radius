# Developer Guide

## Table of Contents

- [Adding a New Detection Rule](#adding-a-new-detection-rule)
- [Adding a New Scoring Rule](#adding-a-new-scoring-rule)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Injecting Sample Events](#injecting-sample-events)
- [Lambda Packaging and Deployment](#lambda-packaging-and-deployment)
- [Shared Backend Modules](#shared-backend-modules)
- [Lambda Environment Variables](#lambda-environment-variables)
- [CI/CD Pipeline](#cicd-pipeline)

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

### Install test dependencies

```bash
pip install -r backend/requirements-dev.txt
```

This installs pytest, pytest-cov, moto, hypothesis, and all other test dependencies. Always run this after cloning or pulling changes that modify `requirements-dev.txt`.

### Run all tests

```bash
bash scripts/run-tests.sh
```

Runs unit tests, integration tests, and property-based tests in sequence and prints a formatted summary table with pass/fail counts, coverage percentages, and duration per suite.

### Fast mode (skip property-based tests)

```bash
bash scripts/run-tests.sh --fast
```

Skips the Hypothesis property-based test suite. Useful during active development when you want a quick feedback loop. Property tests should always be run before committing.

### Run a single test file

```bash
pytest backend/tests/test_remediation_engine.py -v
```

Replace the file path with any test file. The `-v` flag shows individual test names and pass/fail status.

### Interpreting coverage output

After running the full suite, pytest-cov prints a per-module coverage table:

```
Name                                                    Stmts   Miss  Cover
---------------------------------------------------------------------------
backend/functions/detection_engine/engine.py               45      3    93%
backend/functions/remediation_engine/engine.py             82      5    94%
...
TOTAL                                                     612     38    94%
```

- **Stmts** — total executable statements in the module
- **Miss** — statements not executed by any test
- **Cover** — percentage of statements executed

Lines marked with `# pragma: no cover` are excluded from the count (used sparingly for defensive error branches that cannot be triggered in tests).

### Full test suite (legacy pytest invocation)

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

---

## Shared Backend Modules

Logic shared between multiple Lambda functions lives in `backend/common/` and is bundled into every Lambda package by `build-lambdas.sh`. Do not import from one Lambda function's directory into another — use `backend/common/` instead.

| Module | Purpose |
|---|---|
| `backend/common/logging_utils.py` | Structured JSON logger, `put_metric()` for CloudWatch custom metrics |
| `backend/common/dynamodb_utils.py` | DynamoDB client helpers (`get_item`, `put_item`, `update_item`, `query_gsi`) |
| `backend/common/errors.py` | Shared exception types (`ValidationError`, `DynamoDBError`, `EventProcessingError`) |
| `backend/common/aws_utils.py` | CloudTrail event field extraction helpers |
| `backend/common/validation.py` | Input validation utilities |
| `backend/common/incident_utils.py` | `transition_status()` — incident status transition logic shared by `api_handler` and `incident_processor` |
| `backend/common/remediation_config.py` | `load_config()` / `update_risk_mode()` — remediation config access shared by `api_handler` and `remediation_engine` |

### Emitting custom metrics

Use `put_metric()` from `logging_utils` to emit business-logic metrics to the `Radius` CloudWatch namespace:

```python
from backend.common.logging_utils import put_metric

put_metric("ScoresWritten", written, dimensions={"Environment": os.environ["ENVIRONMENT"]})
```

Metric emission is fire-and-forget — all exceptions are swallowed so a CloudWatch API failure never crashes a handler.

---

## Lambda Environment Variables

Every Lambda function receives these environment variables at runtime (injected by Terraform):

| Variable | Description |
|---|---|
| `ENVIRONMENT` | `dev` or `prod` |
| `AWS_ACCOUNT_REGION` | AWS region |
| `LOG_LEVEL` | Log level: `DEBUG`, `INFO`, `WARNING`, or `ERROR` (default `INFO`) |

Additional function-specific variables (DynamoDB table names, ARNs, etc.) are documented in `infra/modules/lambda/main.tf`.

To change `LOG_LEVEL` without a code redeploy, update `log_level` in `terraform.tfvars` and run `deploy-infra.sh`.

---

## CI/CD Pipeline

Two GitHub Actions workflows automate testing and deployment.

### CI (`.github/workflows/ci.yml`)

Runs on every pull request to `main`:
- Python unit + integration tests via `run-tests.sh`
- Frontend build with placeholder env vars (confirms the build compiles)
- `terraform fmt -check -recursive` to catch formatting drift

### Deploy (`.github/workflows/deploy.yml`)

Runs on merge to `main`, requires manual approval via the `production` GitHub environment:
1. Runs the full test suite (gates deployment)
2. Builds Lambda packages and uploads to S3
3. Runs `terraform plan` then `terraform apply`
4. Pulls Cognito and API config from SSM Parameter Store
5. Builds the React frontend with real config values
6. Syncs `frontend/dist/` to the S3 hosting bucket
7. Invalidates the CloudFront cache

Authentication to AWS uses OIDC — no long-lived access keys are stored in GitHub Secrets. The deploy role ARN is stored as `AWS_DEPLOY_ROLE_ARN` in GitHub Secrets.
