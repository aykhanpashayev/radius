# Phase 3 Design: Blast Radius Score Engine

## Overview

Phase 3 replaces the placeholder scoring logic in the existing `Score_Engine` Lambda with a real, rule-based scoring engine. No new AWS services are introduced. No DynamoDB tables are modified. No existing APIs change. The implementation is entirely contained within `backend/functions/score_engine/` and a small extension to `backend/functions/event_normalizer/`.

---

## Architecture

### Component Interactions

```
CloudTrail Event
      │
      ▼
EventBridge Rule
      │
      ▼
Event_Normalizer Lambda
  ├── async → Detection_Engine (unchanged)
  ├── async → Identity_Collector (unchanged)
  └── async → Score_Engine (NEW: single-identity rescore)
                    │
                    ▼
            ScoringContext builder
            (reads Identity_Profile,
             Event_Summary,
             Trust_Relationship,
             Incident tables)
                    │
                    ▼
            RuleEngine.evaluate()
            (runs 8 scoring rules)
                    │
                    ▼
            Blast_Radius_Score table
            (overwrite current snapshot)
```

```
EventBridge Scheduler (every 6h prod / 24h dev)
      │
      ▼
Score_Engine Lambda (batch mode: payload = {})
      │
      ▼
Scan Identity_Profile (is_active=true)
      │
      ▼
For each identity → ScoringContext → RuleEngine → Blast_Radius_Score
```

---

## Score_Engine Internal Design

### Module Structure

```
backend/functions/score_engine/
├── handler.py          # Lambda entry point (extended, not replaced)
├── interfaces.py       # ScoringRule ABC + ScoreResult + classify_severity (extended)
├── rules/
│   ├── __init__.py
│   ├── admin_privileges.py
│   ├── iam_permissions_scope.py
│   ├── iam_modification.py
│   ├── logging_disruption.py
│   ├── cross_account_trust.py
│   ├── role_chaining.py
│   ├── privilege_escalation.py
│   └── lateral_movement.py
├── engine.py           # RuleEngine: orchestrates rule evaluation and aggregation
├── context.py          # ScoringContext: fetches and holds data for one identity
└── requirements.txt    # unchanged
```

### ScoringContext

`context.py` is responsible for fetching all data needed to score one identity. It is constructed once per identity and passed to every rule.

```python
@dataclass
class ScoringContext:
    identity_arn: str
    identity_profile: dict          # Identity_Profile record (may be empty dict)
    events: list[dict]              # Event_Summary records, last 90 days, max 1000
    trust_relationships: list[dict] # Trust_Relationship records (source_arn = identity)
    open_incidents: list[dict]      # Incident records with status in {open, investigating}
```

Data retrieval uses existing `dynamodb_utils.py` helpers:
- `identity_profile`: `get_item(IDENTITY_PROFILE_TABLE, {"identity_arn": arn})`
- `events`: paginated query on primary key `identity_arn`, filter `timestamp >= 90_days_ago`, max 1000 items
- `trust_relationships`: query primary key `source_arn = arn`
- `open_incidents`: query `IdentityIndex` GSI with `identity_arn = arn`, then filter `status in {open, investigating}` client-side (IdentityIndex is KEYS_ONLY, so a follow-up `get_item` per incident_id is needed)

### RuleEngine

`engine.py` holds the ordered list of all 8 rules and orchestrates evaluation.

```python
class RuleEngine:
    rules: list[ScoringRule]  # all 8 rules, instantiated once

    def evaluate(self, context: ScoringContext) -> ScoreResult:
        contributions = []
        total = 0
        for rule in self.rules:
            points = rule.calculate(context.identity_arn, context)
            points = max(0, min(points, rule.max_contribution))
            if points > 0:
                contributions.append(f"{rule.rule_name}: +{points}")
                total += points
        total = min(total, 100)
        return ScoreResult(
            identity_arn=context.identity_arn,
            score_value=total,
            severity_level=classify_severity(total),
            calculation_timestamp=utc_now(),
            contributing_factors=contributions,
        )
```

### ScoringRule Interface (extended)

The existing `ScoringRule` ABC in `interfaces.py` is extended with two class-level attributes:

```python
class ScoringRule(ABC):
    rule_id: str
    rule_name: str
    max_contribution: int   # NEW: caps this rule's output

    @abstractmethod
    def calculate(self, identity_arn: str, context: ScoringContext) -> int:
        ...
```

The `context` parameter type changes from `dict[str, Any]` to `ScoringContext`. This is a backward-compatible change since the Phase 2 placeholder never called `calculate()`.

---

## Scoring Rules Design

Each rule is a stateless class. Rules only read from the `ScoringContext`; they never call DynamoDB directly.

### Rule 1: AdminPrivileges (`admin_privileges`)

```
max_contribution = 25

IAM_WRITE_EVENTS = {CreateUser, CreateRole, AttachUserPolicy, AttachRolePolicy,
                    PutUserPolicy, PutRolePolicy, CreatePolicy, CreatePolicyVersion}

points = 0
if any event.event_type in IAM_WRITE_EVENTS → points += 20
if len(distinct services across all events) >= 5 → points += 5
return min(points, 25)
```

Service is extracted from `event_type` by splitting on `:` (e.g., `iam:CreateUser` → `iam`).

### Rule 2: IAMPermissionsScope (`iam_permissions_scope`)

```
max_contribution = 20

iam_events = [e for e in events if e.event_type starts with "iam:"]
distinct_actions = len({e.event_type for e in iam_events})

if distinct_actions == 0 → 0
if 1 <= distinct_actions <= 4 → 5
if 5 <= distinct_actions <= 9 → 10
if distinct_actions >= 10 → 20
```

### Rule 3: IAMModification (`iam_modification`)

```
max_contribution = 20

IAM_MUTATION_EVENTS = {AttachUserPolicy, AttachRolePolicy, AttachGroupPolicy,
                       PutUserPolicy, PutRolePolicy, PutGroupPolicy,
                       CreatePolicyVersion, SetDefaultPolicyVersion, AddUserToGroup}

count = len([e for e in events if event_name(e) in IAM_MUTATION_EVENTS])

if count == 0 → 0
if 1 <= count <= 2 → 10
if count >= 3 → 20
```

`event_name(e)` extracts the action part from `event_type` (e.g., `iam:AttachUserPolicy` → `AttachUserPolicy`).

### Rule 4: LoggingDisruption (`logging_disruption`)

```
max_contribution = 20

LOGGING_DISRUPTION_EVENTS = {StopLogging, DeleteTrail, UpdateTrail, PutEventSelectors,
                              DeleteFlowLogs, DeleteLogGroup, DeleteLogStream}

if any event_name(e) in LOGGING_DISRUPTION_EVENTS → 20
else → 0
```

### Rule 5: CrossAccountTrust (`cross_account_trust`)

```
max_contribution = 15

cross_account = [t for t in trust_relationships
                 if t.relationship_type == "CrossAccount"]
count = len(cross_account)

if count == 0 → 0
if count == 1 → 5
if 2 <= count <= 3 → 10
if count >= 4 → 15
```

### Rule 6: RoleChaining (`role_chaining`)

```
max_contribution = 10

ASSUME_ROLE_EVENTS = {AssumeRole, AssumeRoleWithSAML, AssumeRoleWithWebIdentity}

count = len([e for e in events if event_name(e) in ASSUME_ROLE_EVENTS])

if count == 0 → 0
if 1 <= count <= 2 → 5
if count >= 3 → 10
```

### Rule 7: PrivilegeEscalation (`privilege_escalation`)

```
max_contribution = 15

ESCALATION_EVENTS = {CreatePolicyVersion, AddUserToGroup, PassRole}

indicators = 0

# Indicator 1: CreateUser followed by AttachUserPolicy in same window
event_names = [event_name(e) for e in events]
if "CreateUser" in event_names and "AttachUserPolicy" in event_names:
    indicators += 1

# Indicator 2: CreatePolicyVersion present
if "CreatePolicyVersion" in event_names:
    indicators += 1

# Indicator 3: AddUserToGroup present
if "AddUserToGroup" in event_names:
    indicators += 1

# Indicator 4: PassRole present
if "PassRole" in event_names:
    indicators += 1

if indicators == 0 → 0
if indicators == 1 → 8
if indicators >= 2 → 15
```

### Rule 8: LateralMovement (`lateral_movement`)

```
max_contribution = 10

points = 0

# Cross-account AssumeRole
identity_account = extract_account_id(identity_arn)  # from backend/common/aws_utils.py
cross_account_assumes = [
    e for e in events
    if event_name(e) == "AssumeRole"
    and extract_target_account(e) != identity_account
]
if cross_account_assumes → points += 5

# EC2 instance profile usage
if any event_name(e) == "RunInstances" for e in events → points += 3

# Federation events
FEDERATION_EVENTS = {GetFederationToken, AssumeRoleWithWebIdentity}
if any event_name(e) in FEDERATION_EVENTS for e in events → points += 2

return min(points, 10)
```

`extract_target_account(e)` reads `e.get("event_parameters", {}).get("roleArn", "")` and extracts the account ID from the ARN. Note: the Event_Normalizer normalizes `requestParameters.roleArn` into `event_parameters.roleArn` — this field must be present in the normalized Event_Summary record.

---

## Handler Design (extended)

`handler.py` is extended to replace the placeholder logic. The public interface (`lambda_handler` signature, environment variables, return shape) is preserved.

```python
def lambda_handler(event, context):
    correlation_id = generate_correlation_id()
    identity_arn = event.get("identity_arn")

    if identity_arn:
        arns = [identity_arn]
    else:
        arns = _scan_active_identities()   # unchanged from Phase 2

    engine = RuleEngine()
    written, failures = 0, 0

    for arn in arns:
        try:
            ctx = ScoringContext.build(arn)   # fetches all data
            if not ctx.identity_profile:
                logger.warning("Identity_Profile not found, skipping", ...)
                continue
            previous = _get_previous_score(arn)
            result = engine.evaluate(ctx)
            if previous:
                result.previous_score = previous["score_value"]
                result.score_change = result.score_value - previous["score_value"]
            _write_score(result)
            written += 1
        except Exception as exc:
            log_error(...)
            failures += 1

    return {"status": "ok", "records_written": written, "failures": failures}
```

---

## Event_Normalizer Extension

`event_normalizer/handler.py` is extended to invoke Score_Engine after processing each event. The existing invocations of Detection_Engine and Identity_Collector are unchanged.

```python
# After existing async invocations:
_invoke_async(SCORE_ENGINE_FUNCTION_NAME, {"identity_arn": identity_arn})
```

A new environment variable `SCORE_ENGINE_FUNCTION_NAME` is added to the Event_Normalizer Lambda configuration in Terraform.

---

## Terraform Changes

### EventBridge Scheduler Rule

A new scheduled rule is added to `infra/modules/eventbridge/main.tf`:

```hcl
resource "aws_cloudwatch_event_rule" "score_engine_schedule" {
  name                = "${var.prefix}-score-engine-schedule"
  schedule_expression = var.score_engine_schedule   # "rate(6 hours)" prod, "rate(24 hours)" dev
  description         = "Periodic batch rescoring of all active identities"
}

resource "aws_cloudwatch_event_target" "score_engine_schedule_target" {
  rule = aws_cloudwatch_event_rule.score_engine_schedule.name
  arn  = var.score_engine_function_arn
}
```

New variables added to `infra/modules/eventbridge/variables.tf`:
- `score_engine_schedule` (string, default `"rate(6 hours)"`)
- `score_engine_function_arn` (string)

### Lambda Environment Variables

The Event_Normalizer Lambda resource in `infra/modules/lambda/main.tf` gains one new environment variable:
- `SCORE_ENGINE_FUNCTION_NAME` — the Score_Engine function name

The Score_Engine Lambda IAM role in `infra/modules/lambda/iam.tf` gains read permissions for:
- `Identity_Profile` table (already has this)
- `Event_Summary` table (new: query by identity_arn)
- `Trust_Relationship` table (new: query by source_arn)
- `Incident` table (new: query IdentityIndex GSI)

The Event_Normalizer Lambda IAM role gains:
- `lambda:InvokeFunction` permission for the Score_Engine function (new)

---

## Data Flow: Single-Identity Rescore

```
1. CloudTrail event arrives → EventBridge → Event_Normalizer
2. Event_Normalizer normalizes event, writes Event_Summary
3. Event_Normalizer invokes Score_Engine async: {"identity_arn": "arn:aws:iam::123:user/alice"}
4. Score_Engine builds ScoringContext for alice:
   - reads Identity_Profile[alice]
   - queries Event_Summary[alice] last 90 days (up to 1000 events)
   - queries Trust_Relationship[source=alice]
   - queries IdentityIndex[alice] → fetches open incidents
5. RuleEngine evaluates 8 rules against context
6. Score_Engine reads existing Blast_Radius_Score[alice] for previous_score
7. Score_Engine writes new Blast_Radius_Score[alice] with score, severity, contributing_factors
8. GET /scores/alice returns updated score with contributing_factors
```

---

## Data Flow: Batch Rescore

```
1. EventBridge Scheduler fires (every 6h prod / 24h dev)
2. Score_Engine invoked with {}
3. Scans Identity_Profile for all is_active=true records
4. For each identity: build context → evaluate rules → write score
5. Returns {"status": "ok", "records_written": N, "failures": M}
```

---

## Scoring Context: DynamoDB Query Patterns

| Data | Table | Query Pattern |
|------|-------|---------------|
| Identity_Profile | Identity_Profile | `get_item(identity_arn)` |
| Recent events | Event_Summary | `query(PK=identity_arn, SK>=90_days_ago)`, paginated, max 1000 |
| Trust edges | Trust_Relationship | `query(PK=source_arn=identity_arn)` |
| Open incidents | Incident | `query(IdentityIndex, PK=identity_arn)` → `get_item` per id |

All queries use existing `dynamodb_utils.py` helpers. No new DynamoDB tables or GSIs are required.

---

## Property-Based Testing Design

Tests use [Hypothesis](https://hypothesis.readthedocs.io/) to generate synthetic `ScoringContext` objects and verify the correctness properties from Requirement 10.

### Test Strategy

| Property | Test Approach |
|----------|---------------|
| Score bounds (0–100) | Generate random contexts, assert `0 <= score <= 100` |
| Severity consistency | Generate random scores, assert `severity == classify_severity(score)` |
| Contributing factors non-negative | Generate contexts, assert all factor points >= 0 |
| Rule independence | For each rule, zero out its inputs, assert score does not increase |
| Determinism | Score same context twice, assert identical results |
| Empty context baseline | Pass empty context, assert score == 0 |
| Score change consistency | Generate previous score, assert `score_change == new - previous` |

### Hypothesis Strategies

```python
# Synthetic event generator
@st.composite
def event_summary(draw):
    return {
        "event_type": draw(st.sampled_from(ALL_EVENT_TYPES)),
        "identity_arn": draw(st.from_regex(ARN_PATTERN)),
        "timestamp": draw(st.datetimes()).isoformat(),
        "event_parameters": draw(st.fixed_dictionaries({
            "roleArn": st.one_of(st.none(), st.from_regex(ARN_PATTERN))
        })),
    }

# Synthetic context generator
@st.composite
def scoring_context(draw):
    arn = draw(st.from_regex(ARN_PATTERN))
    return ScoringContext(
        identity_arn=arn,
        identity_profile={"identity_arn": arn, "is_active": True},
        events=draw(st.lists(event_summary(), max_size=50)),
        trust_relationships=draw(st.lists(trust_relationship(), max_size=10)),
        open_incidents=draw(st.lists(incident(), max_size=5)),
    )
```

---

## File Change Summary

| File | Change |
|------|--------|
| `backend/functions/score_engine/handler.py` | Replace placeholder with real scoring orchestration |
| `backend/functions/score_engine/interfaces.py` | Add `max_contribution` to `ScoringRule`; update `calculate()` signature |
| `backend/functions/score_engine/engine.py` | New: `RuleEngine` class |
| `backend/functions/score_engine/context.py` | New: `ScoringContext` dataclass + `build()` factory |
| `backend/functions/score_engine/rules/` | New: 8 rule modules |
| `backend/common/aws_utils.py` | New: `extract_account_id()` moved here from `identity_collector/collector.py` |
| `backend/functions/event_normalizer/handler.py` | Add async Score_Engine invocation |
| `infra/modules/eventbridge/main.tf` | Add scheduled rule for batch scoring |
| `infra/modules/eventbridge/variables.tf` | Add `score_engine_schedule`, `score_engine_function_arn` |
| `infra/modules/lambda/main.tf` | Add `SCORE_ENGINE_FUNCTION_NAME` env var to Event_Normalizer |
| `infra/modules/lambda/iam.tf` | Extend Score_Engine IAM role; extend Event_Normalizer IAM role |
| `infra/envs/dev/terraform.tfvars` | Add `score_engine_schedule = "rate(24 hours)"` |
| `infra/envs/prod/terraform.tfvars` | Add `score_engine_schedule = "rate(6 hours)"` |
| `backend/tests/test_score_engine_properties.py` | New: property-based tests |
| `backend/tests/test_scoring_rules.py` | New: unit tests for each rule |
| `docs/scoring-model.md` | New: scoring model documentation |
