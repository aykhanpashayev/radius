# Radius

Radius is a cost-aware AWS security platform designed to measure and reduce the **blast radius of identity-based cloud attacks** across large AWS Organizations.

## Problem

Large organizations run hundreds of AWS accounts with thousands of IAM identities and complex trust relationships.

When attackers compromise credentials they often use legitimate AWS APIs to:

- escalate privileges
- assume roles
- disable logging
- access sensitive resources
- launch infrastructure
- move across accounts

Traditional monitoring often detects these actions too late.

## Solution

Radius helps organizations understand:

1. Which identities are most dangerous
2. What suspicious identity activity is happening
3. What incidents require immediate attention
4. How to reduce blast radius before damage spreads

## Core Concept

### Blast Radius Score

Each identity receives a score from **0–100** estimating how damaging it would be if compromised.

Severity levels:

| Score | Severity |
|------|------|
| 0–19 | Low |
| 20–39 | Moderate |
| 40–59 | High |
| 60–79 | Very High |
| 80–100 | Critical |

The scoring model is **fully explainable** and rule-based.

## Architecture Overview

Radius uses a cost-aware event-driven AWS architecture:

- CloudTrail
- EventBridge
- Lambda
- DynamoDB
- API Gateway
- S3
- CloudFront
- SNS

The system monitors identity-related control-plane events and detects suspicious behavior while maintaining identity risk profiles.

## Key Features

- Identity risk scoring
- Suspicious activity detection
- Incident generation
- Cross-account visibility
- Cost-aware architecture
- Explainable security analytics

## Project Status

Currently under development.

Phase roadmap:

1. Planning & Architecture
2. Infrastructure & Backend Foundation
3. Blast Radius Score Engine
4. Detection Rules & Incident Logic
5. Frontend Dashboard
6. Testing & Documentation
7. Remediation Workflows
8. Final Demo & Interview Readiness

## License

MIT