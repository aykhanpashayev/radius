# Phase 2 Scope

Phase 2 establishes the complete infrastructure foundation and service skeletons for Radius. It does **not** implement business logic for detection or scoring — those are deferred to later phases.

## What Phase 2 Includes

- All Terraform infrastructure modules (KMS, DynamoDB, Lambda, EventBridge, API Gateway, CloudTrail, SNS, CloudWatch)
- Dev and prod environment configurations
- Six Lambda function skeletons with correct IAM roles and environment variables
- Event processing pipeline: CloudTrail → EventBridge → Event_Normalizer → Detection_Engine → Incident_Processor
- Identity data collection: Event_Normalizer → Identity_Collector → Identity_Profile + Trust_Relationship
- Incident creation, deduplication, and status management
- SNS alerting for High/Very High/Critical severity incidents
- REST API with 10 operations across 5 resource groups
- CloudWatch alarms, dashboards, and structured logging
- Sample CloudTrail events and testing/seeding scripts
- Documentation stubs completed

## What Phase 2 Excludes

### Detection_Engine (PLACEHOLDER)
Detection_Engine logs received events and defines the `DetectionRule` interface but contains **no real detection rules**. It forwards a placeholder finding to Incident_Processor to keep the pipeline testable. Real detection rules are implemented in Phase 3.

### Score_Engine (PLACEHOLDER — replaced in Phase 3)
Score_Engine logged invocations and defined the `ScoringRule` interface but contained **no real scoring algorithms**. It wrote placeholder Blast_Radius_Score records (score: 50, severity: Moderate) for pipeline and API testing only. Real scoring algorithms were implemented in Phase 3 — see [Phase 3 summary](#phase-3-blast-radius-score-engine) below.

### Identity_Collector (Basic Only)
Identity_Collector records basic trust edges from AssumeRole events and maintains Identity_Profile records. It does **not** perform permission analysis, lateral movement detection, or complex graph traversal — those are Phase 3 features.

### Frontend Dashboard
The React frontend is scaffolded but not implemented in Phase 2.

### Authentication / Authorization
API Gateway uses no authentication in Phase 2 (IAM auth is configured in Terraform but not enforced). Production auth is a Phase 3 concern.

## Phase 2 Success Criteria

1. `terraform validate` passes clean on the root module
2. All Lambda functions deploy and are invocable
3. Sample events injected via `inject-events.py` flow through the pipeline end-to-end
4. API endpoints return 200 or 404 (not 500) for valid requests
5. CloudWatch logs show structured JSON output with correlation IDs
6. SNS alerts fire for Critical/Very High/High severity incidents

---

## Phase 3: Blast Radius Score Engine

Phase 3 replaced the Score_Engine placeholder with a real, rule-based scoring implementation. All Phase 2 infrastructure, tables, and APIs were preserved unchanged.

**Delivered in Phase 3:**

- `ScoringContext` — fetches Identity_Profile, Event_Summary (90-day window), Trust_Relationship, and open Incidents from DynamoDB before any rule runs
- `RuleEngine` — orchestrates 8 independent scoring rules, clamps per-rule contributions, caps total at 100
- 8 scoring rules: AdminPrivileges, IAMPermissionsScope, IAMModification, LoggingDisruption, CrossAccountTrust, RoleChaining, PrivilegeEscalation, LateralMovement
- Score_Engine handler rewritten with real logic — same Lambda interface, same DynamoDB write path
- Event_Normalizer extended to invoke Score_Engine asynchronously per processed event
- EventBridge scheduled rule for periodic batch rescoring (dev: 24h, prod: 6h)
- IAM policy extensions for Score_Engine (read access to Event_Summary, Trust_Relationship, Incident) and Event_Normalizer (invoke Score_Engine)
- 102 tests: unit tests for all rules, RuleEngine, and ScoringContext; property-based tests validating 7 correctness properties via Hypothesis

For the full scoring model reference — rules, thresholds, severity levels, worked example, and invocation modes — see [`docs/scoring-model.md`](scoring-model.md).
