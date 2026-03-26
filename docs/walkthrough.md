# Radius — Project Walkthrough

## Table of Contents

- [Introduction](#introduction)
- [Why I Built Radius](#why-i-built-radius)
- [Architecture Decisions](#architecture-decisions)
- [Detection Engine Design](#detection-engine-design)
- [Scoring Model Design](#scoring-model-design)
- [Remediation Design](#remediation-design)
- [Testing Strategy](#testing-strategy)
- [What I Would Do Differently](#what-i-would-do-differently)
- [Common Interview Questions](#common-interview-questions)

---

## Introduction

This document is an interview-ready narrative of every significant design decision in Radius. It is written for a technical audience — engineers, security practitioners, and hiring managers — who want to understand not just what the system does, but why it was built the way it was. Each section covers the problem being solved, the alternatives considered, and the rationale for the chosen approach. Read it alongside the architecture diagrams in `docs/architecture/` and the API reference in `docs/api-reference.md` for the full picture.

---

## Why I Built Radius

The "blast radius" mental model comes from infrastructure engineering: if a component fails, how much of the system does it take down with it? Applied to IAM, the question becomes — if this identity is compromised, how much damage can an attacker do before anyone notices?

Most AWS security tooling answers with binary alerts: a rule fires or it does not. What is missing is a continuous, explainable risk score that reflects *how dangerous* an identity is right now based on its recent behavior. Tools like Prowler and ScoutSuite audit static IAM configurations well, but they do not track behavioral signals over time and do not produce a score you can explain to a non-specialist.

I built Radius to close that gap: event ingestion from CloudTrail, behavioral detection, explainable scoring, incident tracking, automated remediation, and a React dashboard — wired together with Terraform and validated with property-based tests. The goal was to demonstrate that a solo engineer can design and ship a production-grade security platform, not just a proof-of-concept script.

---

## Architecture Decisions

### (a) Serverless Lambda + DynamoDB vs Containerized Services

The alternative was ECS tasks or Kubernetes pods running a persistent detection service backed by RDS.

I chose Lambda + DynamoDB for three reasons. First, the workload is bursty — CloudTrail events spike during business hours and are nearly silent overnight. Lambda scales to zero between events, so the cost model matches actual usage. A container running 24/7 to process 8 hours of events wastes roughly two-thirds of its compute budget. Second, Lambda's per-invocation isolation means a bug in one detection rule cannot corrupt another invocation's state. Third, DynamoDB's single-digit millisecond reads suit the lookup-heavy patterns in DetectionContext and ScoringContext, where each invocation needs 2–4 targeted reads rather than complex joins.

The tradeoff is cold start latency. For a security platform, a 200–400ms cold start on an async invocation is acceptable — the event is already captured in CloudTrail, so detection does not need to be synchronous with the original API call.

### (b) Event-Driven Async Invokes vs Synchronous Pipeline

The alternative was a synchronous chain: Event_Normalizer calls Detection_Engine and waits, Detection_Engine calls Incident_Processor and waits.

I chose async invokes for two reasons. First, it decouples pipeline stages so a slow downstream function does not block Event_Normalizer from acknowledging the EventBridge event. EventBridge has a 24-hour retry window, so throttled invocations are not lost. Second, async invokes allow Event_Normalizer to fan out to Detection_Engine and Identity_Collector in parallel rather than sequentially.

The tradeoff is observability. With async invokes there is no single call stack to trace. I addressed this by propagating a `correlation_id` through every invocation payload, enabling CloudWatch Logs Insights queries to reconstruct the full processing chain for any given event.

### (c) DynamoDB vs RDS

The alternative was PostgreSQL on RDS, which enables complex joins across Identity_Profile, Event_Summary, and Incident in a single query.

I chose DynamoDB because every read in the system is either a primary key lookup or a GSI query with a known partition key — there are no ad-hoc analytical queries requiring full scans or multi-table joins. DynamoDB's single-table design discipline forced careful upfront thinking about access patterns, producing a cleaner data model. The operational overhead is also lower: no connection pooling, no VPC placement required for Lambda, no maintenance windows.

The tradeoff is the dashboard's "show all incidents sorted by severity in the last 7 days" query. I addressed this with a `SeverityIndex` GSI on the Incident table, allowing the API to query by severity and sort by creation timestamp without a full scan.

### (d) EventBridge vs Kinesis for CloudTrail Routing

The alternative was a Kinesis Data Stream as the CloudTrail delivery target, with Lambda consuming from the stream.

I chose EventBridge because CloudTrail's native integration requires zero additional infrastructure — no stream, no shard management, no consumer group configuration. EventBridge rules filter events at the source, so only IAM, STS, Organizations, and EC2 control-plane events reach Event_Normalizer. Kinesis would deliver every CloudTrail event to the consumer, requiring in-code filtering.

The tradeoff is throughput. EventBridge's default limit of 10,000 events per second per account is sufficient for a single organization. At very high volumes — 1,000 accounts each generating significant CloudTrail traffic — Kinesis would be the better choice for its ordered, replayable delivery with configurable parallelism. I discuss this in the "What I Would Do Differently" section.

---

## Detection Engine Design

The Detection Engine evaluates seven rules against each normalized CloudTrail event. The rules fall into two types.

**Single-event rules** operate on the event payload alone. They require no DynamoDB reads and are fully deterministic given the event. CrossAccountRoleAssumption, LoggingDisruption, and RootUserActivity are single-event rules. They are fast and cheap — a single Lambda invocation with no I/O.

**Context-aware rules** receive a pre-fetched `DetectionContext` alongside the event. The context contains the identity's events from the last 60 minutes and the distinct services it used in the last 30 days. PrivilegeEscalation, IAMPolicyModificationSpike, APIBurstAnomaly, and UnusualServiceUsage are context-aware rules.

A key design decision was to have `DetectionContext.build()` execute all DynamoDB reads before any rule runs, rather than letting each rule fetch its own data. This means the engine makes exactly two DynamoDB reads per invocation regardless of how many context-aware rules fire. If each rule fetched its own data, a seven-rule engine could make up to fourteen reads per invocation. Pre-fetching also makes rules easier to test — a rule's unit test can pass a fully constructed context dict without mocking DynamoDB.

Deduplication lives in Incident_Processor, not Detection_Engine. Detection_Engine forwards every triggered finding immediately, without checking whether a similar incident already exists. Incident_Processor applies a 24-hour deduplication window keyed on `identity_arn` + `detection_type`. This keeps Detection_Engine stateless — each invocation is independently correct and requires no knowledge of prior invocations. Stateless functions are easier to scale, easier to test, and easier to reason about under failure.

See [docs/detection-rules.md](detection-rules.md) for the full rule reference including trigger conditions and confidence values.

---

## Scoring Model Design

The Blast Radius Score is a deterministic integer from 0 to 100 that quantifies how dangerous an IAM identity would be if compromised. Eight rules contribute to the total; the sum is capped at 100.

**Why rule-based scoring instead of ML?** A machine learning model would require labeled training data (known-malicious vs known-benign identities), a retraining pipeline, and a feature store. More importantly, it would produce a score that is difficult to explain to a security analyst or an auditor. Rule-based scoring trades some accuracy for full explainability: every point in the score is traceable to a named rule and a specific behavioral signal. An analyst looking at a score of 78 can see exactly which rules fired and why.

**Contributing factors** are the mechanism for explainability. Every rule that contributes non-zero points appends a string to the `contributing_factors` list in the format `"RuleName: +N"`. The dashboard displays these factors alongside the score, so an analyst can immediately understand what drove a high score without reading source code.

**The score cap at 100** prevents correlated-indicator inflation. Many of the scoring rules detect overlapping signals — an identity performing privilege escalation will also trigger AdminPrivileges, IAMPermissionsScope, and IAMModification. Without a cap, a single attack sequence could produce a score of 150 or more, which is meaningless. The cap ensures the score remains a bounded risk indicator rather than an unbounded event counter. The severity thresholds (0–19 Low, 20–39 Moderate, 40–59 High, 60–79 Very High, 80–100 Critical) are calibrated against the cap, so a score of 80 always means Critical regardless of how many rules fired.

See [docs/scoring-model.md](scoring-model.md) for the full rule reference including point tables and a worked example.

---

## Remediation Design

The Remediation Engine is invoked asynchronously by Incident_Processor for High, Very High, and Critical severity incidents. It evaluates a configuration-driven rule set and optionally executes approved AWS mutations against the offending IAM identity.

**Three risk modes** give operators control over automation aggressiveness. `monitor` mode logs every evaluation but executes no mutations and sends no notifications — it is the safe default that ships with the system. `alert` mode adds SNS notifications without mutations, allowing operators to validate that the right rules are firing before enabling enforcement. `enforce` mode executes the configured IAM actions. This graduated promotion path means an operator can run the system in production for weeks in monitor mode, review the audit log to confirm the rules match expected incidents, then promote to alert and finally enforce with confidence.

**Four safety controls** prevent runaway automation. Before any rule matching occurs, the engine checks: (1) whether the identity is in the `excluded_arns` list, (2) whether the identity's account is in `protected_account_ids`, (3) whether a remediation was already executed for this identity in the last 60 minutes (cooldown), and (4) whether the identity has exceeded 10 remediations in the last 24 hours (rate limit). Any firing guard suppresses the entire evaluation. These controls exist because automated IAM mutations are high-stakes — a false positive that disables a CI/CD service account can take down a deployment pipeline. The safety controls ensure that even a misconfigured rule set cannot cause unbounded damage.

**The append-only audit log** records every evaluation — executed, skipped, suppressed, or failed — to the `Remediation_Audit_Log` DynamoDB table. Records have a 365-day TTL. The audit log has compliance value beyond debugging: it provides a tamper-evident record of every automated action the system took, which is required by frameworks like SOC 2 and ISO 27001. The `details` field stores action-specific metadata (deactivated key IDs, removed policy ARNs, previous trust policy JSON) so that every automated change can be rolled back manually if needed.

See [docs/remediation.md](remediation.md) for the full operational reference including rollback procedures and rule configuration examples.

---

## Testing Strategy

Radius uses three test layers, each serving a different purpose.

**Unit tests** cover individual functions and classes in isolation. All AWS SDK calls are mocked with `unittest.mock`. Unit tests run in under 10 seconds and require no network access or AWS credentials. They are the primary feedback loop during development — fast enough to run on every file save.

**Integration tests** use [moto](https://github.com/getmoto/moto) to simulate real AWS service behavior in-process. Moto creates actual DynamoDB tables, processes GSI queries, and enforces key schema constraints — behaviors that `unittest.mock` cannot replicate. Integration tests catch bugs at the boundary between application code and the AWS SDK: incorrect key names, missing GSI projections, wrong sort key types. They run in 30–60 seconds and require no AWS credentials.

**Property-based tests** use [Hypothesis](https://hypothesis.readthedocs.io/) to verify invariants that must hold across all possible inputs. Three invariants are tested:

- *Severity ordering* — a score of N always maps to a severity level greater than or equal to the level of score N-1, ensuring thresholds are monotonically consistent.
- *Round-trip serialization* — a `ScoreResult` serialized to DynamoDB format and deserialized back produces an identical object, catching subtle type coercion bugs (e.g., Decimal vs float) that only appear with specific input values.
- *Monitor mode suppression* — when configured in `monitor` mode, no IAM mutations are ever executed regardless of incident severity, rule configuration, or identity type. Hypothesis generates hundreds of random payloads to verify this holds universally.

All three test layers are orchestrated by [`scripts/run-tests.sh`](../scripts/run-tests.sh), which runs them in sequence and prints a summary table with pass counts, failure counts, and coverage percentages.

---

## What I Would Do Differently

### (a) Add Kinesis for High-Volume Environments

EventBridge works well for a single AWS Organization, but at scale — 1,000 accounts each generating significant CloudTrail volume — the per-account EventBridge limits become a constraint. Kinesis Data Streams provides ordered, replayable delivery with configurable parallelism (one Lambda shard per Kinesis shard). A production deployment at enterprise scale would use a Kinesis stream as the CloudTrail delivery target, with EventBridge retained for low-volume environments and local development. The application code would need a thin adapter layer to normalize the Kinesis record envelope into the same event format that Event_Normalizer currently receives from EventBridge.

### (b) Add a Feedback Loop for False-Positive Rate Tracking

The detection rules use static confidence values (60–100) defined by the rule author. There is no mechanism to track whether a triggered finding was a true or false positive. In a production system, analysts would triage incidents and mark them confirmed or dismissed. That signal should feed back into confidence values — a rule with a 40% false-positive rate should have its confidence reduced. This feedback loop would also enable per-account tuning, since a rule that generates noise in one environment might be highly accurate in another.

### (c) Replace Static Confidence Values with Bayesian Updating

Rather than manually adjusting static confidence values, a Bayesian model would update each rule's confidence automatically based on observed outcomes. The prior would be the rule author's initial estimate; each confirmed true positive would increase the posterior, and each false positive would decrease it. This makes the detection engine self-calibrating without manual rule maintenance. The implementation would add a `ConfidenceModel` table storing per-rule Beta distribution parameters, updated by the incident triage workflow.

---

## Common Interview Questions

**Q: How does Radius scale to 1,000 AWS accounts?**

The architecture scales horizontally without code changes. EventBridge delivers events from all accounts to Event_Normalizer, which Lambda scales concurrently. DynamoDB on-demand billing scales automatically. The main constraint at 1,000 accounts is EventBridge's 10,000 events/second regional limit — at that scale I would replace EventBridge with Kinesis. Application code would not change; only the trigger source would.

**Q: What is the cost model at 10 million events per day?**

At 10M events/day, Event_Normalizer receives ~115 invocations/second. At ~200ms and 256MB each, Lambda cost is ~$0.50/day. Each invocation writes one Event_Summary record and triggers two downstream Lambdas — roughly 30M DynamoDB writes/day. At $1.25 per million writes, that is ~$37/day. Score_Engine rescores all active identities on schedule — at 10,000 identities, ~$0.10/run. Total: under $50/day for 10M events, dominated by DynamoDB writes.

**Q: How do you prevent false positives from triggering remediation?**

Three layers of protection. First, remediation rules require a minimum severity threshold — Low and Moderate incidents never trigger remediation. Second, the four safety controls (excluded ARNs, protected accounts, cooldown, rate limit) prevent repeated or unexpected executions. Third, the system ships in `monitor` mode, so no mutations occur until an operator explicitly promotes to `enforce` after reviewing the audit log. The graduated path (monitor → alert → enforce) is the primary safeguard against misconfigured rules.

**Q: How would you add a new detection rule?**

Create a Python file in `backend/functions/detection_engine/rules/` implementing the `DetectionRule` interface: `rule_id`, `rule_name`, `severity`, `confidence`, and an `evaluate(event_summary, context)` method returning a `Finding` or `None`. Register it in `rules/__init__.py`. Write unit tests for the trigger and non-trigger cases. The rule engine discovers rules at startup — no changes to the engine itself are required. If the rule needs context data not currently in `DetectionContext`, add the DynamoDB query to `DetectionContext.build()` and update the context-aware rule tests.

**Q: How do you ensure the audit log is tamper-resistant?**

The `Remediation_Audit_Log` table uses an append-only write pattern: records are written once with a UUID primary key and never updated or deleted (TTL is the only expiry mechanism). The Remediation_Engine IAM role has `dynamodb:PutItem` on the audit table but not `dynamodb:UpdateItem` or `dynamodb:DeleteItem` — the Lambda cannot modify existing records. For stronger compliance guarantees, I would add DynamoDB Streams to export records to S3 with Object Lock (WORM) enabled.

**Q: What is the blast radius of Radius itself being compromised?**

If the Remediation_Engine Lambda's execution role were compromised, an attacker could execute the five remediation actions against any identity in the account. The IAM role is scoped to the minimum permissions required for those actions — it cannot create IAM resources, modify CloudTrail, or access S3. The safety controls (excluded ARNs, protected accounts) still apply because they are evaluated in-code. To reduce this blast radius further, I would split the remediation role into per-action roles and use Lambda resource policies to restrict which functions can invoke Remediation_Engine.

**Q: How would you add real-time streaming to the dashboard?**

Currently the React dashboard polls the REST API. To add real-time updates, I would add an API Gateway WebSocket API. When Incident_Processor creates a new incident, it publishes to an SNS topic that triggers a broadcast Lambda, which pushes the update to all connected dashboard clients. DynamoDB Streams on the Blast_Radius_Score table would trigger score update broadcasts. WebSocket connection IDs would be stored in a DynamoDB table with a short TTL. No changes to the existing REST API or Lambda functions would be required.

**Q: What would change about the scoring model if you had access to AWS Config data?**

AWS Config provides point-in-time snapshots of IAM policy documents, enabling two new scoring dimensions. First, I could score the *static* permissions breadth of an identity — how many actions its attached policies allow — rather than only behavioral signals from CloudTrail. An identity with `iam:*` in its policy is high-risk even if it has never used those permissions. Second, Config's history would allow detecting policy changes over time. I would add two new rules: `StaticPermissionsScope` (scoring allowed-action breadth) and `PolicyDrift` (scoring the rate of policy change over 30 days).
