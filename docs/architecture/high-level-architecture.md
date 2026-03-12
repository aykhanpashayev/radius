# Radius High Level Architecture

Radius is an identity-centric AWS security platform designed for large multi-account AWS Organizations.

## Core Design Principles

- Identity-focused security monitoring
- Event-driven architecture
- Serverless infrastructure
- Cost-aware design
- Explainable security analytics

## Architecture Layers

### Event Collection

AWS CloudTrail management events are used as the primary telemetry source.

### Event Processing

Events are routed through Amazon EventBridge and processed by Lambda functions.

Processing stages:

1. Event Normalization
2. Detection Engine
3. Incident Processor

### Data Storage

DynamoDB stores:

- identity profiles
- blast radius scores
- incidents
- event summaries
- trust relationships

### API Layer

API Gateway provides endpoints for the Radius dashboard.

### Dashboard

A static web dashboard hosted on S3 and served via CloudFront.

### Alerts

SNS is used for critical incident notifications.

## Core AWS Services

- CloudTrail
- EventBridge
- Lambda
- DynamoDB
- API Gateway
- S3
- CloudFront
- SNS