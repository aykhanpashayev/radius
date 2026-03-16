# Radius Architecture

Radius is a serverless, event-driven cloud security platform that measures and reduces the blast radius of identity-based attacks in AWS Organizations.

## Event Processing Pipeline

```
CloudTrail (management events)
    │
    ▼
EventBridge (rule: IAM/STS/Orgs/EC2 events)
    │
    ▼
Event_Normalizer Lambda
    ├──► Detection_Engine Lambda (async invoke)
    │        └──► Incident_Processor Lambda (async invoke)
    │                  └──► SNS Alert_Topic (high-severity only)
    └──► Identity_Collector Lambda (async invoke)
             ├── Identity_Profile table (DynamoDB)
             └── Trust_Relationship table (DynamoDB)
```

Event_Normalizer is the single entry point from EventBridge. It invokes Detection_Engine and Identity_Collector **asynchronously** — neither is triggered directly by EventBridge.

## Lambda Functions

| Function | Trigger | Purpose |
|---|---|---|
| Event_Normalizer | EventBridge | Parse, validate, and store CloudTrail events; fan out to downstream functions |
| Detection_Engine | Async invoke (Event_Normalizer) | PLACEHOLDER — logs events, defines detection interfaces for Phase 3 |
| Incident_Processor | Async invoke (Detection_Engine) | Create/deduplicate incidents; publish SNS alerts |
| Identity_Collector | Async invoke (Event_Normalizer) | Maintain Identity_Profile and Trust_Relationship records |
| Score_Engine | On-demand | PLACEHOLDER — logs invocations, defines scoring interfaces for Phase 3 |
| API_Handler | API Gateway | Serve REST API for all read/write operations |

## Data Flow

1. CloudTrail captures management-plane events across the AWS Organization
2. EventBridge filters IAM, STS, Organizations, and EC2 events and routes them to Event_Normalizer
3. Event_Normalizer normalizes the event, stores an Event_Summary record, then asynchronously invokes Detection_Engine and Identity_Collector
4. Detection_Engine (placeholder) forwards a finding to Incident_Processor
5. Incident_Processor creates or deduplicates an Incident record and publishes SNS alerts for High/Very High/Critical severity
6. Identity_Collector creates or updates Identity_Profile records and records Trust_Relationship edges for AssumeRole events
7. API_Handler serves the React dashboard via API Gateway

## Infrastructure Modules

```
KMS ──────────────────────────────────────────────────────────────────┐
                                                                       │ (encryption keys)
DynamoDB ◄─────────────────────────────────────────────────────────── ┤
SNS      ◄─────────────────────────────────────────────────────────── ┤
Lambda   ◄── DynamoDB table names/ARNs, SNS topic ARN, KMS key ────── ┤
EventBridge ◄── Lambda ARNs ──────────────────────────────────────────┘
API Gateway ◄── Lambda ARN/name
CloudTrail  ◄── KMS key
CloudWatch  ◄── Lambda names, DynamoDB table names, API Gateway name
```

## Design Principles

- **Serverless**: No persistent compute — all processing is Lambda-based
- **Event-driven**: Processing triggered by CloudTrail events, not polling
- **Cost-aware**: On-demand DynamoDB billing, arm64 Lambda, TTL for data expiry
- **Explainable**: Detection and scoring logic is rule-based and transparent
- **Multi-account**: CloudTrail org-wide trail covers all accounts in the Organization
