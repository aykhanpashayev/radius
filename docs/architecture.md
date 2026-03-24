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
    │                                                    ▼
    │                                          SNS Alert_Topic
    │                                       (High / Very High / Critical)
    │
    ├──► Identity_Collector Lambda (async invoke)
    │         ├── Identity_Profile table
    │         └── Trust_Relationship table
    │
    └──► Score_Engine Lambda (EventBridge schedule or direct invoke)
              └── Blast_Radius_Score table

API_Handler Lambda ◄── API Gateway ◄── React Dashboard
    ├── Identity_Profile table
    ├── Blast_Radius_Score table
    ├── Incident table
    └── Event_Summary table
```

Event_Normalizer is the single entry point from EventBridge. It invokes Detection_Engine and Identity_Collector **asynchronously** — neither is triggered directly by EventBridge. Score_Engine runs on an EventBridge schedule (per-identity) or via direct Lambda invoke (batch mode).

## Lambda Functions

| Function | Trigger | Purpose | Downstream |
|---|---|---|---|
| Event_Normalizer | EventBridge rule | Parse and validate CloudTrail events; write Event_Summary; fan out to downstream functions | Detection_Engine, Identity_Collector (async) |
| Detection_Engine | Async invoke (Event_Normalizer) | Evaluate 7 detection rules against event + DetectionContext; emit Findings | Incident_Processor (async) |
| Incident_Processor | Async invoke (Detection_Engine) | Create or deduplicate Incident records; publish SNS alerts for high-severity findings | SNS Alert_Topic |
| Identity_Collector | Async invoke (Event_Normalizer) | Upsert Identity_Profile records; record Trust_Relationship edges for AssumeRole events | — |
| Score_Engine | EventBridge schedule / direct invoke | Evaluate 8 scoring rules against ScoringContext; write Blast_Radius_Score snapshot | — |
| API_Handler | API Gateway (REST) | Serve all read/write operations for the React dashboard | — |

## DynamoDB Tables

| Table | PK | SK | Purpose |
|---|---|---|---|
| Identity_Profile | `identity_arn` | — | IAM identity metadata, type, account, last activity |
| Blast_Radius_Score | `identity_arn` | — | Current score snapshot: value, severity level, contributing factors |
| Incident | `incident_id` | — | Security incidents: status, severity, related events, status history |
| Event_Summary | `identity_arn` | `timestamp` | Normalized CloudTrail events; TTL-expired after 90 days |
| Trust_Relationship | `source_arn` | `target_arn` | Cross-account and service trust edges discovered from AssumeRole events |

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
│   ├── dynamodb/            # All 5 tables with GSIs, TTL, PITR, encryption
│   ├── sns/                 # Alert_Topic with KMS encryption and subscriptions
│   ├── lambda/              # All 6 functions: IAM roles, DLQs, env vars, packaging
│   ├── eventbridge/         # CloudTrail event routing rule + Score_Engine schedule
│   ├── apigateway/          # REST API with Lambda proxy integration and access logging
│   ├── cloudtrail/          # Org-wide management event trail with S3 and KMS
│   └── cloudwatch/          # Alarms (Lambda errors/throttles, DynamoDB throttles) + log groups
└── envs/
    └── dev/                 # Dev environment: tfvars, backend config
```

### Module Dependencies

```
kms
 ├──► dynamodb
 ├──► sns
 ├──► lambda ──► eventbridge
 │           └──► apigateway
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

## Design Principles

- **Serverless** — no persistent compute; all processing is Lambda-based with on-demand DynamoDB billing
- **Event-driven** — processing triggered by CloudTrail events, not polling or continuous scanning
- **Cost-aware** — arm64 Lambda, KEYS_ONLY GSIs where full projection is unnecessary, TTL for Event_Summary and Incident archival
- **Explainable** — detection rules have explicit trigger conditions; scoring rules emit named contributing factors with point values
- **Multi-account** — org-wide CloudTrail trail covers all accounts; account_id is a first-class field on all records
