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

### Score_Engine (PLACEHOLDER)
Score_Engine logs invocations and defines the `ScoringRule` interface but contains **no real scoring algorithms**. It writes placeholder Blast_Radius_Score records (score: 50, severity: Moderate) for pipeline and API testing only. Real scoring algorithms are implemented in Phase 3.

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
