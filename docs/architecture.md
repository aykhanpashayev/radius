# Radius Architecture

Radius is a serverless, event-driven cloud security platform that measures and reduces the blast radius of identity-based attacks in AWS Organizations.

## Event Processing Pipeline

```
CloudTrail (org-wide management events)
    │
    ▼
EventBridge (rule: IAM / STS / Organizations / EC2 control-plane events)
    │
    ▼
Event_Normalizer Lambda
    ├──► Detection_Engine Lambda ──────────► Incident_Processor Lambda
    │         (async invoke)                       (async invoke)
    │                                                    │
    │                                                    ├──► SNS Alert_Topic
    │                                                    │  (High / Very High / Critical)
    │                                                    │
    │                                                    └──► Remediation_Engine Lambda (async)
    │
    ├──► Identity_Collector Lambda (async invoke)
    │         ├── Identity_Profile table
    │         └── Trust_Relationship table
    │
    └──► Score_Engine Lambda (EventBridge schedule or direct invoke)
              └── Blast_Radius_Score table

React Dashboard ──► Cognito (login) ──► JWT token
                                            │
                                            ▼
                                    API Gateway (Cognito authorizer)
                                            │
                                            ▼
                                    API_Handler Lambda
                                        ├── Identity_Profile table
                                        ├── Blast_Radius_Score table
                                        ├── Incident table
                                        ├── Event_Summary table
                                        ├── Remediation_Config table
                                        └── Remediation_Audit_Log table
```

Event_Normalizer is the single entry point from EventBridge. It invokes Detection_Engine and Identity_Collector **asynchronously** — neither is triggered directly by EventBridge. Score_Engine runs on an EventBridge schedule (per-identity) or via direct Lambda invoke (batch mode).

All API Gateway endpoints (except OPTIONS preflight) require a valid Cognito JWT in the `Authorization` header.

## Lambda Functions

| Function | Trigger | Purpose | Downstream |
|---|---|---|---|
| Event_Normalizer | EventBridge rule | Parse and validate CloudTrail events; write Event_Summary; fan out to downstream functions | Detection_Engine, Identity_Collector (async) |
| Detection_Engine | Async invoke (Event_Normalizer) | Evaluate 7 detection rules against event + DetectionContext; emit Findings | Incident_Processor (async) |
| Incident_Processor | Async invoke (Detection_Engine) | Create or deduplicate Incident records; publish SNS alerts for high-severity findings | SNS Alert_Topic |
| Identity_Collector | Async invoke (Event_Normalizer) | Upsert Identity_Profile records; record Trust_Relationship edges for AssumeRole events | — |
| Score_Engine | EventBridge schedule / direct invoke | Evaluate 8 scoring rules against ScoringContext; write Blast_Radius_Score snapshot | — |
| API_Handler | API Gateway (REST) | Serve all read/write operations for the React dashboard | — |
| Remediation_Engine | Async invoke (Incident_Processor) | Evaluate remediation rules against high-severity incidents; execute approved IAM actions; write audit log | Remediation_Topic (SNS) |

## DynamoDB Tables

| Table | PK | SK | Purpose |
|---|---|---|---|
| Identity_Profile | `identity_arn` | — | IAM identity metadata, type, account, last activity |
| Blast_Radius_Score | `identity_arn` | — | Current score snapshot: value, severity level, contributing factors |
| Incident | `incident_id` | — | Security incidents: status, severity, related events, status history |
| Event_Summary | `identity_arn` | `timestamp` | Normalized CloudTrail events; TTL-expired after 90 days |
| Trust_Relationship | `source_arn` | `target_arn` | Cross-account and service trust edges discovered from AssumeRole events |
| Remediation_Config | `config_id` | — | Singleton remediation config: Risk_Mode, active rules, exclusion lists |
| Remediation_Audit_Log | `audit_id` | — | Append-only audit trail of every remediation action evaluation; TTL 365 days |

### GSIs

**Identity_Profile**
- `IdentityTypeIndex` — PK: `identity_type`, SK: `account_id` (ALL)
- `AccountIndex` — PK: `account_id`, SK: `last_activity_timestamp` (ALL)

**Blast_Radius_Score**
- `ScoreRangeIndex` — PK: `severity_level`, SK: `score_value` (ALL)
- `SeverityIndex` — PK: `severity_level`, SK: `calculation_timestamp` (KEYS_ONLY)

**Incident**
- `StatusIndex` — PK: `status`, SK: `creation_timestamp` (ALL)
- `SeverityIndex` — PK: `severity`, SK: `creation_timestamp` (ALL)
- `IdentityIndex` — PK: `identity_arn`, SK: `creation_timestamp` (KEYS_ONLY) — used by deduplication

**Event_Summary**
- `EventIdIndex` — PK: `event_id` (ALL)
- `EventTypeIndex` — PK: `event_type`, SK: `timestamp` (KEYS_ONLY)
- `TimeRangeIndex` — PK: `date_partition`, SK: `timestamp` (ALL)

**Trust_Relationship**
- `RelationshipTypeIndex` — PK: `relationship_type`, SK: `discovery_timestamp` (ALL)
- `TargetAccountIndex` — PK: `target_account_id`, SK: `discovery_timestamp` (KEYS_ONLY)

## Terraform Module Structure

```
infra/
├── main.tf                  # Root module — composes all service modules
├── modules/
│   ├── kms/                 # KMS keys for DynamoDB, SNS, Lambda, CloudTrail
│   ├── cognito/             # Cognito User Pool, App Client, hosted domain
│   ├── dynamodb/            # All 7 tables with GSIs, TTL, PITR, encryption
│   ├── sns/                 # Alert_Topic and Remediation_Topic with KMS encryption
│   ├── lambda/              # All 7 functions: IAM roles, DLQs, env vars, packaging
│   ├── eventbridge/         # CloudTrail event routing rule + Score_Engine schedule
│   ├── apigateway/          # REST API, Cognito authorizer, usage plan, throttling
│   ├── cloudtrail/          # Org-wide management event trail with S3 and KMS
│   └── cloudwatch/          # Alarms (infra + business-logic) + dashboards + log groups
└── envs/
    ├── dev/                 # Dev environment: tfvars, backend config
    └── prod/                # Prod environment: tfvars, backend config
```

### Module Dependencies

```
kms, cognito
 ├──► dynamodb
 ├──► sns
 ├──► lambda ──► eventbridge
 │           └──► apigateway (receives cognito.user_pool_arn)
 └──► cloudtrail
          └──► cloudwatch (consumes all resource names/ARNs)
```

## Data Flow

1. CloudTrail captures management-plane events across the AWS Organization
2. EventBridge filters IAM, STS, Organizations, and EC2 events and routes them to Event_Normalizer
3. Event_Normalizer validates the event, writes an Event_Summary record to DynamoDB, then asynchronously invokes Detection_Engine and Identity_Collector
4. Detection_Engine builds a DetectionContext (recent events, prior services) and evaluates 7 rules; each Finding is forwarded to Incident_Processor
5. Incident_Processor deduplicates against existing open incidents (24-hour window keyed on `identity_arn` + `detection_type`), creates or updates an Incident record, and publishes an SNS alert for High/Very High/Critical severity
6. Identity_Collector upserts the Identity_Profile record and writes a Trust_Relationship edge for AssumeRole events
7. Score_Engine (scheduled or on-demand) builds a ScoringContext and evaluates 8 rules to produce a Blast_Radius_Score snapshot with contributing factors
8. API_Handler serves the React dashboard via API Gateway with endpoints for identities, scores, incidents, and events

## Remediation Workflows

When Incident_Processor creates a High, Very High, or Critical severity incident, it asynchronously invokes the Remediation_Engine Lambda. The engine evaluates a configuration-driven rule set and optionally executes approved AWS mutations against the offending IAM identity.

### Pipeline Branch

```
Incident_Processor Lambda
    │
    ├── (existing) create_incident() → Incident table
    ├── (existing) publish_alert()   → SNS Alert_Topic
    │
    └── _invoke_remediation()        → Remediation_Engine Lambda (async, High+ only)
                                              │
                                              ├── load_config()          → Remediation_Config table
                                              ├── check_safety_controls()
                                              ├── match_rules()
                                              ├── execute_actions()      → IAM APIs
                                              ├── publish_notification() → Remediation_Topic (SNS)
                                              └── write_audit_log()      → Remediation_Audit_Log table
```

### Risk Modes

The engine operates in one of three modes, configured via the `PUT /remediation/config/mode` API:

| Mode | Behaviour |
|---|---|
| `monitor` | All rules evaluated and logged; no AWS mutations, no SNS notifications. Safe default. |
| `alert` | Rules evaluated; SNS notification published; no AWS mutations. |
| `enforce` | Rules evaluated; AWS mutations executed; SNS notification published. |

The `dry_run` flag (Lambda env var or per-invocation payload field) overrides any configured mode to `monitor`.

### Remediation Lambda

| Function | Trigger | Purpose |
|---|---|---|
| Remediation_Engine | Async invoke (Incident_Processor) | Evaluate remediation rules, execute approved IAM actions, write audit log |

### Remediation DynamoDB Tables

| Table | PK | GSIs | Purpose |
|---|---|---|---|
| Remediation_Config | `config_id` | — | Singleton config record: Risk_Mode, active rules, exclusion lists |
| Remediation_Audit_Log | `audit_id` | `IdentityTimeIndex` (PK: `identity_arn`, SK: `timestamp`, ALL); `IncidentIndex` (PK: `incident_id`, SK: `timestamp`, KEYS_ONLY) | Append-only audit trail of every action evaluation; TTL 365 days |

### Remediation SNS Topic

| Topic | Purpose |
|---|---|
| Remediation_Topic | Remediation-specific notifications published in `alert` and `enforce` modes |

### Safety Controls

Before any rule matching, the engine checks four guards in order:

1. `excluded_arns` — identity explicitly excluded from all remediation
2. `protected_account_ids` — identity belongs to a protected AWS account
3. 60-minute cooldown — a remediation was already executed for this identity recently
4. 24-hour rate limit — maximum 10 executions per identity per day

Any firing guard suppresses the entire evaluation and writes a single audit entry with the suppression reason.

---

## Design Principles

- **Serverless** — no persistent compute; all processing is Lambda-based with on-demand DynamoDB billing
- **Event-driven** — processing triggered by CloudTrail events, not polling or continuous scanning
- **Cost-aware** — arm64 Lambda, KEYS_ONLY GSIs where full projection is unnecessary, TTL for Event_Summary and Incident archival
- **Explainable** — detection rules have explicit trigger conditions; scoring rules emit named contributing factors with point values
- **Multi-account** — org-wide CloudTrail trail covers all accounts; account_id is a first-class field on all records

## Diagrams

Detailed Mermaid diagrams for each subsystem are available in `docs/architecture/`:

- [Pipeline Overview](architecture/pipeline-overview.md) — full event pipeline from CloudTrail to the React Dashboard
- [Scoring Pipeline](architecture/scoring-pipeline.md) — Score_Engine trigger sources, ScoringContext queries, and the 8 scoring rules
- [Remediation Branch](architecture/remediation-branch.md) — Remediation_Engine safety controls, rule matching, and risk mode execution paths
- [API Layer](architecture/api-layer.md) — React Dashboard through API Gateway to API_Handler and all DynamoDB tables
