# Changelog

All notable changes to Radius are documented here.

## [1.0.0] — 2026-04-05

Initial production release.

### Infrastructure
- 7 Lambda functions (Python 3.11, arm64): Event_Normalizer, Detection_Engine, Incident_Processor, Identity_Collector, Score_Engine, API_Handler, Remediation_Engine
- 7 DynamoDB tables with GSIs, TTL, PITR, and KMS encryption
- API Gateway REST API with Cognito JWT authorizer, throttling, and CORS on all endpoints
- Cognito User Pool with admin-only user creation and 1-hour token expiry
- CloudFront + S3 frontend hosting with HTTPS and SPA routing
- SNS Alert_Topic and Remediation_Topic
- EventBridge rules for CloudTrail event routing and Score_Engine scheduling
- CloudTrail org-wide management event trail
- KMS keys per service (DynamoDB, Lambda, SNS, CloudTrail)
- CloudWatch alarms: infrastructure (Lambda errors, DynamoDB throttles, DLQ depth, API 5xx) and business-logic (no scores in 6h, no incidents in 72h, scoring failure rate)
- GitHub Actions CI/CD with OIDC (no long-lived AWS keys)
- SSM Parameter Store for all config values consumed by CI/CD

### Backend
- 7 detection rules: privilege escalation, root user activity, cross-account role assumption, IAM policy modification spike, logging disruption, API burst anomaly, unusual service usage
- 8 scoring rules: admin privileges, cross-account trust, IAM modification, IAM permissions scope, lateral movement, logging disruption, privilege escalation, role chaining
- Remediation engine with 5 actions: disable_iam_user, remove_risky_policies, block_role_assumption, restrict_network_access, notify_security_team
- Safety controls: excluded ARNs, protected account IDs, 60-minute cooldown, 24-hour rate limit
- Three risk modes: monitor, alert, enforce
- Dry-run mode (default in dev) — audit log written, no IAM mutations
- Immutable audit log with 365-day TTL

### Frontend
- React 18 + Vite dashboard with Cognito authentication
- Identity risk table with blast radius scores and severity badges
- Incident feed with status transitions
- Identity detail view
- Error boundary — no white screens on component crashes

### Security fixes applied
- API Gateway: all endpoints require Cognito JWT (no unauthenticated access)
- CORS: OPTIONS mock integrations on every resource, GatewayResponse headers on 401/403
- DRY_RUN configurable via Terraform (not hardcoded)
- LOG_LEVEL configurable via Terraform
- No secrets or credentials in repository
- tfvars files gitignored; `.example` templates committed instead
