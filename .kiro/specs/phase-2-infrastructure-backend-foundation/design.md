# Design Document: Phase 2 Infrastructure and Backend Foundation

## Overview

Phase 2 of Radius establishes the complete infrastructure foundation and service skeletons for the cloud security platform. This phase focuses on creating a production-ready serverless architecture with event-driven processing, comprehensive observability, and API access—without implementing detection or scoring business logic.

### Phase 2 Objectives

1. Provision all AWS infrastructure using modular Terraform
2. Establish CloudTrail → EventBridge → Lambda → DynamoDB event pipeline
3. Create Lambda function skeletons with proper IAM roles and configuration
4. Implement DynamoDB tables with optimized GSI access patterns
5. Deploy REST API with pagination and filtering capabilities
6. Configure comprehensive monitoring, logging, and alerting
7. Provide sample data and testing infrastructure

### What Phase 2 Includes

- Complete Terraform module structure with dev/prod environments
- Five DynamoDB tables with 13 Global Secondary Indexes
- Six Lambda functions with IAM roles and CloudWatch integration
- CloudTrail configuration with EventBridge routing
- API Gateway with 11 REST endpoints (10 routes, 11 operations including PATCH)
- SNS alerting infrastructure
- CloudWatch dashboards, metrics, and alarms
- Sample CloudTrail events and injection scripts
- Comprehensive documentation

### What Phase 2 Explicitly Excludes

- Detection rules and suspicious behavior analysis (Detection_Engine is a placeholder)
- Scoring algorithms and risk calculations (Score_Engine is a placeholder)
- Complex trust relationship analysis (Identity_Collector records basic edges only)
- Business intelligence and advanced analytics
- Frontend dashboard implementation

## Architecture

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AWS Organization                               │
│                                                                          │
│  ┌──────────────┐                                                       │
│  │  CloudTrail  │ (Management Events)                                   │
│  │   Trail      │                                                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│         │ Events                                                        │
│         ▼                                                               │
│  ┌──────────────┐         ┌─────────────────────────────────┐         │
│  │      S3      │         │        EventBridge              │         │
│  │  Log Bucket  │         │      (Event Router)             │         │
│  └──────────────┘         └──────────┬──────────────────────┘         │
│                                      │                                  │
│                                      │ Filtered Events                  │
│                                      ▼                                  │
│                           ┌──────────────────┐                         │
│                           │ Event_Normalizer │                         │
│                           │     Lambda       │                         │
│                           └────────┬─────────┘                         │
│                                    │                                    │
│                    ┌───────────────┼───────────────┐                   │
│                    │               │               │                   │
│                    ▼               ▼               ▼                   │
│         ┌──────────────────┐  ┌──────────┐  ┌──────────────────┐     │
│         │ Event_Summary    │  │Detection │  │Identity_Collector│     │
│         │   DynamoDB       │  │ Engine   │  │     Lambda       │     │
│         └──────────────────┘  │ Lambda   │  └────────┬─────────┘     │
│                               │(Placeholder)         │                 │
│                               └────┬─────┘           │                 │
│                                    │                 │                 │
│                                    ▼                 ▼                 │
│                          ┌──────────────┐  ┌──────────────────┐       │
│                          │  Incident    │  │ Identity_Profile │       │
│                          │  Processor   │  │    DynamoDB      │       │
│                          │   Lambda     │  └──────────────────┘       │
│                          └──────┬───────┘                             │
│                                 │                                      │
│                    ┌────────────┼────────────┐                        │
│                    │            │            │                        │
│                    ▼            ▼            ▼                        │
│         ┌──────────────┐  ┌─────────┐  ┌──────────────────┐         │
│         │   Incident   │  │   SNS   │  │Trust_Relationship│         │
│         │   DynamoDB   │  │  Topic  │  │    DynamoDB      │         │
│         └──────────────┘  └─────────┘  └──────────────────┘         │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │                    Score_Engine Lambda                    │        │
│  │                     (Placeholder)                         │        │
│  │  Scheduled/On-Demand ──► Blast_Radius_Score DynamoDB     │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │                     API Gateway                           │        │
│  │  /identities  /scores  /incidents  /events  /trust-rels  │        │
│  └────────────────────────┬─────────────────────────────────┘        │
│                           │                                            │
│                           ▼                                            │
│                  ┌──────────────────┐                                 │
│                  │   API_Handler    │                                 │
│                  │     Lambda       │                                 │
│                  └────────┬─────────┘                                 │
│                           │                                            │
│                           │ Queries                                    │
│                           ▼                                            │
│              ┌────────────────────────────┐                           │
│              │   All DynamoDB Tables      │                           │
│              │   (Read Access via GSIs)   │                           │
│              └────────────────────────────┘                           │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────┐        │
│  │              CloudWatch Observability                     │        │
│  │  Logs │ Metrics │ Alarms │ Dashboards                    │        │
│  └──────────────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────────────┘
```

### Event Processing Flow

1. **CloudTrail Capture**: Management events from all AWS accounts (prod) or single account (dev)
2. **EventBridge Routing**: Filter IAM, STS, Organizations, EC2 events → Event_Normalizer
3. **Normalization**: Parse CloudTrail format → standardized Event_Summary → DynamoDB
4. **Async Invocations from Event_Normalizer**:
   - Event_Normalizer invokes Detection_Engine asynchronously (logs only, no detection logic)
   - Event_Normalizer invokes Identity_Collector asynchronously to update Identity_Profile and Trust_Relationship tables
5. **Incident Creation**: Detection_Engine → Incident_Processor → Incident DynamoDB + SNS alerts (placeholder findings for pipeline testing)
6. **Score Calculation**: Score_Engine (scheduled/on-demand) → Blast_Radius_Score DynamoDB (placeholder values)
7. **API Access**: Frontend → API Gateway → API_Handler → DynamoDB queries via GSIs

### Component Responsibilities

| Component | Responsibility | Phase 2 Status |
|-----------|---------------|----------------|
| CloudTrail | Capture AWS API activity | Fully implemented |
| EventBridge | Route events to processors | Fully implemented |
| Event_Normalizer | Parse and standardize events | Fully implemented |
| Detection_Engine | Identify suspicious behavior | **Placeholder - logs only** |
| Incident_Processor | Create and manage incidents | Fully implemented (handles placeholder findings for pipeline testing) |
| Identity_Collector | Maintain identity profiles | Basic implementation |
| Score_Engine | Calculate blast radius scores | **Placeholder - arbitrary values** |
| API_Handler | Serve data to frontend | Fully implemented |
| DynamoDB Tables | Store all system data | Fully implemented |
| SNS | Alert on high-severity incidents | Fully implemented |
| CloudWatch | Observability and monitoring | Fully implemented |

## Terraform Design

### Module Structure

```
infra/
├── main.tf                    # Root module composition
├── variables.tf               # Root-level variables
├── outputs.tf                 # Root-level outputs
├── backend.tf                 # S3 + DynamoDB state backend
├── versions.tf                # Provider version constraints
├── envs/
│   ├── dev/
│   │   ├── main.tf           # Dev environment configuration
│   │   ├── terraform.tfvars  # Dev-specific values
│   │   └── backend.tfvars    # Dev state backend config
│   └── prod/
│       ├── main.tf           # Prod environment configuration
│       ├── terraform.tfvars  # Prod-specific values
│       └── backend.tfvars    # Prod state backend config
└── modules/
    ├── lambda/
    │   ├── main.tf           # Lambda function resources
    │   ├── variables.tf      # Function config inputs
    │   ├── outputs.tf        # Function ARNs and names
    │   └── iam.tf            # IAM roles and policies
    ├── dynamodb/
    │   ├── main.tf           # Table definitions
    │   ├── variables.tf      # Table config inputs
    │   ├── outputs.tf        # Table names and ARNs
    │   └── gsi.tf            # GSI definitions
    ├── eventbridge/
    │   ├── main.tf           # EventBridge rules
    │   ├── variables.tf      # Rule config inputs
    │   └── outputs.tf        # Rule ARNs
    ├── apigateway/
    │   ├── main.tf           # API Gateway resources
    │   ├── variables.tf      # API config inputs
    │   ├── outputs.tf        # API endpoint URLs
    │   └── endpoints.tf      # Endpoint definitions
    ├── cloudtrail/
    │   ├── main.tf           # CloudTrail trail
    │   ├── variables.tf      # Trail config inputs
    │   ├── outputs.tf        # Trail ARN and bucket
    │   └── s3.tf             # S3 bucket for logs
    ├── sns/
    │   ├── main.tf           # SNS topics
    │   ├── variables.tf      # Topic config inputs
    │   └── outputs.tf        # Topic ARNs
    ├── cloudwatch/
    │   ├── main.tf           # Log groups
    │   ├── variables.tf      # Monitoring config inputs
    │   ├── outputs.tf        # Log group names
    │   ├── alarms.tf         # CloudWatch alarms
    │   └── dashboards.tf     # CloudWatch dashboards
    └── kms/
        ├── main.tf           # KMS keys
        ├── variables.tf      # Key config inputs
        └── outputs.tf        # Key ARNs and IDs
```

### Root Module Design

The root module at `infra/` composes all service modules and manages cross-module dependencies.

**Key Responsibilities:**
- Instantiate all service modules with appropriate configurations
- Pass outputs from one module as inputs to dependent modules
- Define environment-agnostic resource naming patterns
- Manage data sources for AWS account information

**Module Composition Pattern:**
```hcl
module "kms" {
  source = "./modules/kms"
  environment = var.environment
  prefix = var.resource_prefix
}

module "dynamodb" {
  source = "./modules/dynamodb"
  environment = var.environment
  prefix = var.resource_prefix
  kms_key_arn = module.kms.dynamodb_key_arn
}

module "lambda" {
  source = "./modules/lambda"
  environment = var.environment
  prefix = var.resource_prefix
  dynamodb_table_names = module.dynamodb.table_names
  sns_topic_arn = module.sns.alert_topic_arn
  kms_key_arn = module.kms.lambda_key_arn
}
```

### Environment Configuration

**Dev Environment (`infra/envs/dev/`):**
- Single AWS account CloudTrail
- Minimal resource provisioning (lower memory, concurrency limits)
- 7-day log retention
- On-demand DynamoDB billing
- Cost-optimized settings
- Sample data injection enabled

**Prod Environment (`infra/envs/prod/`):**
- Organization-wide CloudTrail
- High availability configuration
- 30-day log retention
- Point-in-time recovery enabled
- Production-grade alarms and monitoring
- Sample data injection disabled

**Environment-Specific Variables:**
```hcl
# Dev
environment = "dev"
resource_prefix = "radius-dev"
lambda_memory = {
  event_normalizer = 512
  detection_engine = 1024
  incident_processor = 512
  identity_collector = 512
  score_engine = 1024
  api_handler = 256
}
lambda_concurrency_limit = 10
log_retention_days = 7
cloudtrail_organization_enabled = false

# Prod
environment = "prod"
resource_prefix = "radius-prod"
lambda_memory = {
  event_normalizer = 1024
  detection_engine = 2048
  incident_processor = 1024
  identity_collector = 1024
  score_engine = 2048
  api_handler = 512
}
lambda_concurrency_limit = 100
log_retention_days = 30
cloudtrail_organization_enabled = true
```

### Module Input/Output Design

#### Lambda Module

**Inputs:**
- `environment` (string): Environment name (dev/prod)
- `prefix` (string): Resource naming prefix
- `function_configs` (map): Memory, timeout, concurrency per function
- `dynamodb_table_names` (map): Table names for environment variables
- `sns_topic_arn` (string): Alert topic ARN
- `kms_key_arn` (string): KMS key for encryption
- `log_retention_days` (number): CloudWatch log retention

**Outputs:**
- `function_arns` (map): Lambda function ARNs for EventBridge targets
- `function_names` (map): Function names for monitoring
- `role_arns` (map): IAM role ARNs for auditing

#### DynamoDB Module

**Inputs:**
- `environment` (string): Environment name
- `prefix` (string): Resource naming prefix
- `billing_mode` (string): PAY_PER_REQUEST or PROVISIONED
- `enable_pitr` (bool): Point-in-time recovery flag
- `kms_key_arn` (string): KMS key for encryption
- `ttl_enabled` (bool): Enable TTL for Event_Summary and Incident

**Outputs:**
- `table_names` (map): Table names for Lambda environment variables
- `table_arns` (map): Table ARNs for IAM policies
- `gsi_names` (map): GSI names for query optimization

#### EventBridge Module

**Inputs:**
- `environment` (string): Environment name
- `prefix` (string): Resource naming prefix
- `lambda_function_arns` (map): Target Lambda ARNs
- `event_filters` (list): Event patterns for routing

**Outputs:**
- `rule_arns` (list): EventBridge rule ARNs
- `event_bus_arn` (string): Event bus ARN

#### API Gateway Module

**Inputs:**
- `environment` (string): Environment name
- `prefix` (string): Resource naming prefix
- `lambda_function_arn` (string): API_Handler Lambda ARN
- `cors_allowed_origins` (list): CORS configuration
- `enable_logging` (bool): API Gateway logging flag

**Outputs:**
- `api_endpoint` (string): API Gateway invoke URL
- `api_id` (string): API Gateway ID
- `api_arn` (string): API Gateway ARN

### Remote State Design

**S3 Backend Configuration:**
```hcl
terraform {
  backend "s3" {
    bucket         = "radius-terraform-state-${account_id}"
    key            = "${environment}/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    kms_key_id     = "arn:aws:kms:us-east-1:${account_id}:key/${key_id}"
    dynamodb_table = "radius-terraform-locks"
  }
}
```

**State Locking:**
- DynamoDB table with `LockID` as partition key
- Prevents concurrent Terraform operations
- Automatic lock acquisition and release

**State Management Best Practices:**
- Separate state files per environment
- Encrypted at rest using KMS
- Versioning enabled on S3 bucket
- Lifecycle policy for old state versions

### Logical Dependency Relationships

The following represents the logical dependency relationships between Terraform modules. Terraform automatically resolves the creation order via resource references, so separate sequential applies are not required.

**Dependency Graph:**

1. **KMS Module**: Encryption keys (no dependencies)
2. **DynamoDB Module**: Tables (depends on KMS keys)
3. **SNS Module**: Alert topics (depends on KMS keys)
4. **Lambda Module**: Functions (depends on DynamoDB table names, SNS topic ARNs, KMS keys)
5. **EventBridge Module**: Rules (depends on Lambda function ARNs)
6. **API Gateway Module**: Endpoints (depends on Lambda function ARNs)
7. **CloudTrail Module**: Trail (depends on EventBridge configuration, S3 bucket, KMS keys)
8. **CloudWatch Module**: Alarms and dashboards (depends on all resource ARNs)

**Terraform Behavior:**
- Terraform analyzes resource references and creates a dependency graph automatically
- Resources are created in parallel where possible (e.g., DynamoDB and SNS can be created simultaneously)
- A single `terraform apply` handles the entire deployment
- Understanding this dependency graph helps with troubleshooting and module design


## DynamoDB Design

### Table Overview

| Table | Primary Key | GSI Count | Purpose |
|-------|-------------|-----------|---------|
| Identity_Profile | identity_arn (PK) | 2 | IAM identity metadata and activity history |
| Blast_Radius_Score | identity_arn (PK) | 2 | Risk scores for identities |
| Incident | incident_id (PK) | 3 | Security incidents requiring investigation |
| Event_Summary | identity_arn (PK), timestamp (SK) | 3 | Normalized CloudTrail events |
| Trust_Relationship | source_arn (PK), target_arn (SK) | 2 | Cross-account and service trust edges |

### Identity_Profile Table

**Purpose:** Store metadata and activity history for IAM identities (users, roles, services).

**Primary Key:**
- **PK:** `identity_arn` (String) - Full ARN of the identity

**Attributes:**
- `identity_arn` (String): Full IAM identity ARN
- `identity_type` (String): IAMUser | AssumedRole | AWSService
- `account_id` (String): AWS account ID extracted from ARN
- `creation_date` (String): ISO 8601 timestamp of identity creation
- `last_activity_timestamp` (String): ISO 8601 timestamp of most recent activity
- `tags` (Map): Key-value pairs from identity tags
- `is_active` (Boolean): Whether identity is currently active
- `activity_count` (Number): Total number of observed events

**Global Secondary Indexes:**

1. **IdentityTypeIndex**
   - **PK:** `identity_type` (String)
   - **SK:** `account_id` (String)
   - **Projection:** ALL
   - **Use Case:** Query all identities of a specific type within an account
   - **Example Query:** "Get all IAM users in account 123456789012"

2. **AccountIndex**
   - **PK:** `account_id` (String)
   - **SK:** `last_activity_timestamp` (String)
   - **Projection:** ALL
   - **Use Case:** Query all identities in an account sorted by recent activity
   - **Example Query:** "Get most recently active identities in account 123456789012"

**Access Patterns:**
- Get identity by ARN (primary key lookup)
- List identities by type and account (IdentityTypeIndex)
- List identities by account sorted by activity (AccountIndex)
- Filter identities by active status (scan with filter)

**TTL Configuration:** None (profiles retained indefinitely, marked inactive on deletion)

### Blast_Radius_Score Table

**Purpose:** Store calculated blast radius scores for identities.

**Primary Key:**
- **PK:** `identity_arn` (String) - Full ARN of the identity

**Attributes:**
- `identity_arn` (String): Full IAM identity ARN
- `score_value` (Number): Numeric score 0-100
- `severity_level` (String): Low | Moderate | High | Very High | Critical
- `calculation_timestamp` (String): ISO 8601 timestamp of score calculation
- `contributing_factors` (List): Factors that influenced the score
- `previous_score` (Number): Previous score value for trend analysis
- `score_change` (Number): Delta from previous score

**Severity Ranges:**
- 0-19: Low
- 20-39: Moderate
- 40-59: High
- 60-79: Very High
- 80-100: Critical

**Global Secondary Indexes:**

1. **ScoreRangeIndex**
   - **PK:** `severity_level` (String)
   - **SK:** `score_value` (Number)
   - **Projection:** ALL
   - **Use Case:** Query identities by severity level sorted by score
   - **Example Query:** "Get all Critical severity identities sorted by score descending"

2. **SeverityIndex**
   - **PK:** `severity_level` (String)
   - **SK:** `calculation_timestamp` (String)
   - **Projection:** KEYS_ONLY
   - **Use Case:** Count identities by severity level over time
   - **Example Query:** "Get count of High severity identities calculated today"

**Access Patterns:**
- Get score by identity ARN (primary key lookup)
- List scores by severity level sorted by value (ScoreRangeIndex)
- List scores by severity level sorted by calculation time (SeverityIndex)
- Filter scores by value range (ScoreRangeIndex with query conditions)

**TTL Configuration:** None

**Phase 2 Scope:** This table stores the **current score snapshot only** for each identity. Each new score calculation overwrites the previous value. Historical score tracking and trend analysis will be implemented in future phases when scoring logic is added.

### Incident Table

**Purpose:** Track security incidents requiring investigation.

**Primary Key:**
- **PK:** `incident_id` (String) - UUID v4 format

**Attributes:**
- `incident_id` (String): Unique incident identifier (UUID)
- `identity_arn` (String): Identity involved in the incident
- `detection_type` (String): Type of suspicious behavior detected
- `severity` (String): Low | Moderate | High | Very High | Critical
- `confidence` (Number): Detection confidence score 0-100
- `status` (String): open | investigating | resolved | false_positive
- `creation_timestamp` (String): ISO 8601 timestamp of incident creation
- `update_timestamp` (String): ISO 8601 timestamp of last update
- `related_event_ids` (List): Event IDs associated with this incident
- `status_history` (List): History of status changes with timestamps
- `notes` (String): Investigation notes
- `assigned_to` (String): Security analyst assigned to incident

**Global Secondary Indexes:**

1. **StatusIndex**
   - **PK:** `status` (String)
   - **SK:** `creation_timestamp` (String)
   - **Projection:** ALL
   - **Use Case:** Query incidents by status sorted by creation time
   - **Example Query:** "Get all open incidents sorted by newest first"

2. **SeverityIndex**
   - **PK:** `severity` (String)
   - **SK:** `creation_timestamp` (String)
   - **Projection:** ALL
   - **Use Case:** Query incidents by severity sorted by creation time
   - **Example Query:** "Get all Critical incidents sorted by newest first"

3. **IdentityIndex**
   - **PK:** `identity_arn` (String)
   - **SK:** `creation_timestamp` (String)
   - **Projection:** KEYS_ONLY
   - **Use Case:** Query all incidents for a specific identity
   - **Example Query:** "Get incident count for identity arn:aws:iam::123456789012:user/alice"

**Access Patterns:**
- Get incident by ID (primary key lookup)
- List incidents by status sorted by time (StatusIndex)
- List incidents by severity sorted by time (SeverityIndex)
- List incidents for an identity (IdentityIndex)
- Update incident status (primary key update)

**TTL Configuration:** 
- Attribute: `ttl_timestamp`
- Resolved incidents archived after 90 days
- Open/investigating incidents never expire

**Deduplication Logic:** Before creating an incident, check for existing incidents with same identity_arn and detection_type within 24 hours.

### Event_Summary Table

**Purpose:** Store normalized CloudTrail events for analysis and audit.

**Primary Key:**
- **PK:** `identity_arn` (String) - Identity that performed the action
- **SK:** `timestamp` (String) - ISO 8601 timestamp with microsecond precision

**Attributes:**
- `event_id` (String): CloudTrail event ID (unique identifier)
- `identity_arn` (String): Identity that performed the action
- `event_type` (String): CloudTrail eventName (e.g., CreateUser, AssumeRole)
- `timestamp` (String): ISO 8601 timestamp
- `source_ip` (String): Source IP address
- `user_agent` (String): User agent string
- `event_parameters` (Map): Relevant event parameters (resource ARNs, actions)
- `date_partition` (String): Date in YYYY-MM-DD format for time-range queries
- `account_id` (String): Account where event occurred
- `region` (String): AWS region

**Global Secondary Indexes:**

1. **EventIdIndex**
   - **PK:** `event_id` (String)
   - **Projection:** ALL
   - **Use Case:** Direct event lookup by CloudTrail event ID
   - **Example Query:** "Get event details for event ID abc123-def456-ghi789"
   - **Rationale:** Supports operational troubleshooting and incident investigation when only event ID is known

2. **EventTypeIndex**
   - **PK:** `event_type` (String)
   - **SK:** `timestamp` (String)
   - **Projection:** KEYS_ONLY
   - **Use Case:** Query events by type sorted by time
   - **Example Query:** "Get all AssumeRole events in the last hour"

3. **TimeRangeIndex**
   - **PK:** `date_partition` (String)
   - **SK:** `timestamp` (String)
   - **Projection:** ALL
   - **Use Case:** Efficient time-range queries across all identities
   - **Example Query:** "Get all events on 2024-01-15 between 10:00 and 11:00"

**Access Patterns:**
- Get events for identity in time range (primary key query with SK condition)
- Get event by event ID (EventIdIndex query)
- Get events by type in time range (EventTypeIndex query)
- Get all events in date range (TimeRangeIndex query)

**TTL Configuration:**
- Attribute: `ttl_timestamp`
- Events expire after 90 days (configurable per environment)
- Reduces storage costs for high-volume event data

**Data Exclusion:** Large payloads (>10KB) and sensitive fields (passwords, keys) excluded to minimize storage costs.

### Trust_Relationship Table

**Purpose:** Record cross-account and service-to-service trust relationships.

**Primary Key:**
- **PK:** `source_arn` (String) - Source identity ARN
- **SK:** `target_arn` (String) - Target resource ARN

**Attributes:**
- `source_arn` (String): Source identity ARN (who assumes)
- `target_arn` (String): Target resource ARN (what is assumed)
- `relationship_type` (String): AssumeRole | ServicePrincipal | CrossAccount
- `permissions_granted` (List): List of permission actions (basic only in Phase 2)
- `discovery_timestamp` (String): ISO 8601 timestamp when relationship was first observed
- `last_used_timestamp` (String): ISO 8601 timestamp of most recent use
- `is_active` (Boolean): Whether relationship is currently active
- `source_account_id` (String): Source account ID
- `target_account_id` (String): Target account ID

**Global Secondary Indexes:**

1. **RelationshipTypeIndex**
   - **PK:** `relationship_type` (String)
   - **SK:** `discovery_timestamp` (String)
   - **Projection:** ALL
   - **Use Case:** Query relationships by type sorted by discovery time
   - **Example Query:** "Get all CrossAccount relationships discovered this week"

2. **TargetAccountIndex**
   - **PK:** `target_account_id` (String)
   - **SK:** `discovery_timestamp` (String)
   - **Projection:** KEYS_ONLY
   - **Use Case:** Query relationships targeting a specific account
   - **Example Query:** "Get count of relationships targeting account 123456789012"

**Access Patterns:**
- Get relationships for source identity (primary key query)
- Get specific relationship (primary key lookup)
- List relationships by type (RelationshipTypeIndex)
- List relationships by target account (TargetAccountIndex)

**TTL Configuration:** None (relationships retained for historical analysis)

**Phase 2 Note:** Identity_Collector records only basic trust edges (source → target) without analyzing permissions, transitive relationships, or risk assessment.

### DynamoDB Configuration

**Billing Mode:** On-demand (PAY_PER_REQUEST) for all tables
- Automatically scales with traffic
- No capacity planning required
- Cost-effective for variable workloads

**Encryption:** All tables encrypted at rest using AWS KMS
- Separate KMS keys per environment
- Key rotation enabled

**Point-in-Time Recovery (PITR):**
- Enabled for: Identity_Profile, Blast_Radius_Score, Incident
- Disabled for: Event_Summary (high volume, TTL enabled), Trust_Relationship (can be rebuilt)

**Backup Strategy:**
- PITR provides continuous backups for 35 days
- Manual snapshots before major changes
- Cross-region replication for prod (future phase)


## Lambda Design

### Function Overview

| Function | Memory | Timeout | Trigger | Purpose |
|----------|--------|---------|---------|---------|
| Event_Normalizer | 512MB | 30s | EventBridge | Parse CloudTrail events |
| Detection_Engine | 1024MB | 60s | Event_Normalizer | Detect suspicious behavior (placeholder) |
| Incident_Processor | 512MB | 30s | Detection_Engine | Create and manage incidents |
| Identity_Collector | 512MB | 30s | EventBridge | Maintain identity profiles |
| Score_Engine | 1024MB | 60s | Scheduled/On-demand | Calculate blast radius scores (placeholder) |
| API_Handler | 256MB | 10s | API Gateway | Serve data to frontend |

### Event_Normalizer Lambda

**Responsibility:** Transform CloudTrail events into standardized Event_Summary format.

**Trigger:** EventBridge rule matching IAM, STS, Organizations, EC2 management events

**Input Format:**
```json
{
  "version": "0",
  "id": "event-id",
  "detail-type": "AWS API Call via CloudTrail",
  "source": "aws.iam",
  "account": "123456789012",
  "time": "2024-01-15T10:30:00Z",
  "region": "us-east-1",
  "detail": {
    "eventVersion": "1.08",
    "eventID": "abc123-def456",
    "eventName": "CreateUser",
    "eventTime": "2024-01-15T10:30:00Z",
    "userIdentity": {
      "type": "IAMUser",
      "arn": "arn:aws:iam::123456789012:user/admin",
      "accountId": "123456789012"
    },
    "sourceIPAddress": "203.0.113.42",
    "userAgent": "aws-cli/2.13.0",
    "requestParameters": {
      "userName": "newuser"
    },
    "responseElements": {
      "user": {
        "arn": "arn:aws:iam::123456789012:user/newuser"
      }
    }
  }
}
```

**Processing Logic:**
1. Validate required fields (eventName, userIdentity, eventTime)
2. Extract identity ARN from userIdentity
3. Normalize timestamp to ISO 8601
4. Parse event-specific parameters (resource ARNs, actions)
5. Exclude sensitive data (passwords, keys) and large payloads (>10KB)
6. Generate date_partition for TimeRangeIndex (YYYY-MM-DD)
7. Store Event_Summary in DynamoDB
8. Invoke Detection_Engine asynchronously
9. Invoke Identity_Collector asynchronously (for identity-related events)

**Output Format (Event_Summary):**
```json
{
  "event_id": "abc123-def456",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "event_type": "CreateUser",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "source_ip": "203.0.113.42",
  "user_agent": "aws-cli/2.13.0",
  "event_parameters": {
    "userName": "newuser",
    "targetArn": "arn:aws:iam::123456789012:user/newuser"
  },
  "date_partition": "2024-01-15",
  "account_id": "123456789012",
  "region": "us-east-1"
}
```

**Environment Variables:**
- `EVENT_SUMMARY_TABLE`: DynamoDB table name
- `DETECTION_ENGINE_ARN`: Lambda ARN to invoke
- `IDENTITY_COLLECTOR_ARN`: Lambda ARN to invoke
- `AWS_REGION`: AWS region

**IAM Permissions:**
- `dynamodb:PutItem` on Event_Summary table
- `lambda:InvokeFunction` on Detection_Engine and Identity_Collector
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

**Error Handling:**
- Missing required fields: Log error, skip event, continue processing
- DynamoDB write failure: Retry with exponential backoff (3 attempts)
- Lambda invocation failure: Log error, send to DLQ
- Validation errors: Log with full event context

**Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:01.234Z",
  "level": "INFO",
  "correlation_id": "abc123-def456",
  "function": "event_normalizer",
  "message": "Event normalized successfully",
  "event_id": "abc123-def456",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "event_type": "CreateUser"
}
```

### Detection_Engine Lambda (Placeholder)

**Responsibility:** Identify suspicious behavior patterns (Phase 2: logging only, no detection logic).

**Trigger:** Invoked asynchronously by Event_Normalizer

**Input Format:** Event_Summary object (same as Event_Normalizer output)

**Phase 2 Processing Logic:**
1. Log received event with event_id, identity_arn, event_type
2. Log placeholder message: "Detection logic not implemented in Phase 2"
3. Forward Event_Summary to Incident_Processor for pipeline testing
4. Return success

**Interface Definitions (for future implementation):**

```python
# Detection rule interface
class DetectionRule:
    rule_id: str
    rule_name: str
    severity: str  # Low, Moderate, High, Very High, Critical
    
    def evaluate(self, event: EventSummary, context: DetectionContext) -> Optional[Finding]:
        """Evaluate event against detection rule."""
        pass

# Detection finding structure
class Finding:
    identity_arn: str
    detection_type: str
    severity: str
    confidence: float  # 0-100
    related_event_ids: List[str]
    evidence: Dict[str, Any]
    timestamp: str
```

**Output Format (Finding - for future use):**
```json
{
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "detection_type": "privilege_escalation",
  "severity": "High",
  "confidence": 85.5,
  "related_event_ids": ["abc123-def456", "ghi789-jkl012"],
  "evidence": {
    "pattern": "rapid_permission_changes",
    "event_count": 5,
    "time_window_seconds": 300
  },
  "timestamp": "2024-01-15T10:30:05.000Z"
}
```

**Environment Variables:**
- `INCIDENT_PROCESSOR_ARN`: Lambda ARN to invoke
- `EVENT_SUMMARY_TABLE`: DynamoDB table name (for context queries)
- `AWS_REGION`: AWS region

**IAM Permissions:**
- `dynamodb:Query` on Event_Summary table
- `lambda:InvokeFunction` on Incident_Processor
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

**Phase 2 Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:02.123Z",
  "level": "INFO",
  "correlation_id": "abc123-def456",
  "function": "detection_engine",
  "message": "Detection Engine placeholder - no detection logic in Phase 2",
  "event_id": "abc123-def456",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "event_type": "CreateUser"
}
```

### Incident_Processor Lambda

**Responsibility:** Create and manage security incidents, send alerts for high-severity incidents.

**Trigger:** Invoked asynchronously by Detection_Engine

**Input Format:** Finding object (from Detection_Engine)

**Processing Logic:**
1. Validate required fields (identity_arn, detection_type, severity)
2. Check for duplicate incidents (same identity + detection type within 24 hours)
3. If duplicate exists, update existing incident with new event IDs
4. If new incident, generate UUID v4 incident_id
5. Create Incident record in DynamoDB with status "open"
6. If severity is High, Very High, or Critical, publish to SNS Alert_Topic
7. Log incident creation with incident_id and correlation_id

**Deduplication Logic:**
```python
# Query IdentityIndex for incidents with same identity_arn
# Filter by detection_type and creation_timestamp within last 24 hours
# If found, append related_event_ids and update update_timestamp
# If not found, create new incident
```

**Output Format (Incident):**
```json
{
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "detection_type": "privilege_escalation",
  "severity": "High",
  "confidence": 85.5,
  "status": "open",
  "creation_timestamp": "2024-01-15T10:30:05.000Z",
  "update_timestamp": "2024-01-15T10:30:05.000Z",
  "related_event_ids": ["abc123-def456", "ghi789-jkl012"],
  "status_history": [
    {
      "status": "open",
      "timestamp": "2024-01-15T10:30:05.000Z"
    }
  ],
  "notes": "",
  "assigned_to": ""
}
```

**SNS Alert Format:**
```json
{
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "detection_type": "privilege_escalation",
  "severity": "High",
  "confidence": 85.5,
  "creation_timestamp": "2024-01-15T10:30:05.000Z",
  "dashboard_link": "https://radius-dashboard.example.com/incidents/550e8400-e29b-41d4-a716-446655440000"
}
```

**SNS Message Attributes:**
```json
{
  "severity": {
    "DataType": "String",
    "StringValue": "High"
  },
  "detection_type": {
    "DataType": "String",
    "StringValue": "privilege_escalation"
  }
}
```

**Environment Variables:**
- `INCIDENT_TABLE`: DynamoDB table name
- `ALERT_TOPIC_ARN`: SNS topic ARN
- `DASHBOARD_BASE_URL`: Dashboard URL for incident links
- `DEDUPLICATION_WINDOW_HOURS`: Deduplication time window (default: 24)
- `AWS_REGION`: AWS region

**IAM Permissions:**
- `dynamodb:PutItem`, `dynamodb:UpdateItem` on Incident table
- `dynamodb:Query` on Incident table (IdentityIndex)
- `sns:Publish` on Alert_Topic
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

**Status Transitions:**
- `open` → `investigating`: Manual update via API
- `investigating` → `resolved`: Manual update via API
- `open` → `false_positive`: Manual update via API
- All transitions recorded in status_history

**Error Handling:**
- Missing required fields: Log error, return failure
- DynamoDB write failure: Retry with exponential backoff (3 attempts)
- SNS publish failure: Log error but don't fail incident creation
- Duplicate check failure: Create new incident (fail open)

### Identity_Collector Lambda

**Responsibility:** Maintain Identity_Profile and Trust_Relationship tables based on observed CloudTrail events.

**Trigger:** Invoked asynchronously by Event_Normalizer for identity-related events

**Input Format:** Event_Summary object

**Processing Logic:**
1. Extract identity_arn from Event_Summary
2. Parse identity_type from ARN (IAMUser, AssumedRole, AWSService)
3. Extract account_id from ARN
4. Update or create Identity_Profile:
   - Set last_activity_timestamp to event timestamp
   - Increment activity_count
   - Update tags if present in event metadata
5. If event_type is AssumeRole:
   - Extract target role ARN from event_parameters
   - Create or update Trust_Relationship record
   - Set relationship_type to "AssumeRole"
   - Update last_used_timestamp
6. If event_type is identity deletion (DeleteUser, DeleteRole):
   - Mark Identity_Profile as inactive (is_active = false)

**Identity Type Extraction:**
```python
# ARN format: arn:aws:iam::123456789012:user/alice
# ARN format: arn:aws:sts::123456789012:assumed-role/MyRole/session
# ARN format: arn:aws:iam::123456789012:role/MyRole

def extract_identity_type(arn: str) -> str:
    if ":user/" in arn:
        return "IAMUser"
    elif ":assumed-role/" in arn or ":role/" in arn:
        return "AssumedRole"
    elif ":root" in arn:
        return "Root"
    else:
        return "AWSService"
```

**Trust Relationship Creation (AssumeRole events):**
```python
# Event: AssumeRole
# source_arn: userIdentity.arn (who assumed)
# target_arn: requestParameters.roleArn (what was assumed)
# relationship_type: "AssumeRole"
# permissions_granted: ["sts:AssumeRole"] (basic only in Phase 2)
```

**Phase 2 Limitations:**
- No permission analysis beyond basic action recording
- No transitive relationship traversal
- No risk assessment of trust relationships
- No graph analysis or path finding

**Environment Variables:**
- `IDENTITY_PROFILE_TABLE`: DynamoDB table name
- `TRUST_RELATIONSHIP_TABLE`: DynamoDB table name
- `AWS_REGION`: AWS region

**IAM Permissions:**
- `dynamodb:PutItem`, `dynamodb:UpdateItem` on Identity_Profile table
- `dynamodb:PutItem`, `dynamodb:UpdateItem` on Trust_Relationship table
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

**Error Handling:**
- ARN parsing failure: Log error, skip update
- DynamoDB write failure: Retry with exponential backoff (3 attempts)
- Missing event fields: Log warning, continue with available data

### Score_Engine Lambda (Placeholder)

**Responsibility:** Calculate blast radius scores for identities (Phase 2: placeholder values only).

**Trigger:** Scheduled (daily) or on-demand invocation

**Input Format:**
```json
{
  "identity_arns": [
    "arn:aws:iam::123456789012:user/alice",
    "arn:aws:iam::123456789012:role/MyRole"
  ]
}
```

**Phase 2 Processing Logic:**
1. Log invocation with identity_arns and timestamp
2. For each identity_arn:
   - Query Identity_Profile to verify identity exists
   - Create Blast_Radius_Score record with placeholder values:
     - score_value: 50 (arbitrary)
     - severity_level: "Moderate"
     - calculation_timestamp: current time
     - contributing_factors: ["placeholder"]
3. Log score creation
4. Return success

**Interface Definitions (for future implementation):**

```python
# Scoring rule interface
class ScoringRule:
    rule_id: str
    rule_name: str
    weight: float  # 0-1, contribution to final score
    
    def calculate(self, identity: IdentityProfile, context: ScoringContext) -> float:
        """Calculate score component for this rule."""
        pass

# Scoring context
class ScoringContext:
    trust_relationships: List[TrustRelationship]
    recent_incidents: List[Incident]
    permission_scope: Dict[str, Any]
    activity_patterns: Dict[str, Any]
```

**Severity Classification:**
```python
def classify_severity(score: float) -> str:
    if score < 20:
        return "Low"
    elif score < 40:
        return "Moderate"
    elif score < 60:
        return "High"
    elif score < 80:
        return "Very High"
    else:
        return "Critical"
```

**Output Format (Blast_Radius_Score):**
```json
{
  "identity_arn": "arn:aws:iam::123456789012:user/alice",
  "score_value": 50,
  "severity_level": "Moderate",
  "calculation_timestamp": "2024-01-15T10:30:00.000Z",
  "contributing_factors": ["placeholder"],
  "previous_score": null,
  "score_change": 0
}
```

**Environment Variables:**
- `BLAST_RADIUS_SCORE_TABLE`: DynamoDB table name
- `IDENTITY_PROFILE_TABLE`: DynamoDB table name (for context)
- `AWS_REGION`: AWS region

**IAM Permissions:**
- `dynamodb:Query` on Identity_Profile table
- `dynamodb:PutItem` on Blast_Radius_Score table
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

**Phase 2 Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "function": "score_engine",
  "message": "Score Engine placeholder - arbitrary values in Phase 2",
  "identity_arn": "arn:aws:iam::123456789012:user/alice",
  "score_value": 50,
  "severity_level": "Moderate"
}
```

### API_Handler Lambda

**Responsibility:** Process API Gateway requests and serve data from DynamoDB tables.

**Trigger:** API Gateway proxy integration

**Input Format (API Gateway Proxy Event):**
```json
{
  "httpMethod": "GET",
  "path": "/identities",
  "queryStringParameters": {
    "identity_type": "IAMUser",
    "account_id": "123456789012",
    "limit": "25",
    "next_token": "base64_encoded_last_key"
  },
  "pathParameters": null,
  "headers": {
    "Authorization": "AWS4-HMAC-SHA256 ..."
  },
  "requestContext": {
    "requestId": "abc123-def456",
    "identity": {
      "userArn": "arn:aws:iam::123456789012:user/dashboard-user"
    }
  }
}
```

**Endpoint Handlers:**

1. **GET /identities**
   - Query parameters: identity_type, account_id, limit, next_token
   - GSI: IdentityTypeIndex (if identity_type provided) or AccountIndex (if account_id provided)
   - Default limit: 25, max: 100

2. **GET /identities/{arn}**
   - Path parameter: arn (URL-encoded identity ARN)
   - Primary key lookup
   - Return 404 if not found

3. **GET /scores**
   - Query parameters: severity_level, min_score, max_score, limit, next_token
   - GSI: ScoreRangeIndex (if severity_level provided)
   - Default limit: 25, max: 100

4. **GET /scores/{arn}**
   - Path parameter: arn (URL-encoded identity ARN)
   - Primary key lookup
   - Return 404 if not found

5. **GET /incidents**
   - Query parameters: status, severity, identity_arn, start_date, end_date, limit, next_token
   - GSI: StatusIndex (if status provided) or SeverityIndex (if severity provided) or IdentityIndex (if identity_arn provided)
   - Default limit: 25, max: 100

6. **GET /incidents/{id}**
   - Path parameter: id (incident UUID)
   - Primary key lookup
   - Return 404 if not found

7. **PATCH /incidents/{id}**
   - Path parameter: id (incident UUID)
   - Request body: {"status": "investigating", "notes": "Investigating..."}
   - Update status and append to status_history
   - Return updated incident

8. **GET /events**
   - Query parameters: identity_arn, event_type, start_date, end_date, limit, next_token
   - GSI: EventTypeIndex (if event_type provided) or TimeRangeIndex (if date range provided)
   - Primary key query (if identity_arn provided)
   - Default limit: 25, max: 100

9. **GET /events/{id}**
   - Path parameter: id (event ID)
   - GSI: EventIdIndex query
   - Return 404 if not found

10. **GET /trust-relationships**
    - Query parameters: source_arn, target_account_id, relationship_type, limit, next_token
    - Primary key query (if source_arn provided) or GSI: TargetAccountIndex (if target_account_id provided) or RelationshipTypeIndex (if relationship_type provided)
    - Default limit: 25, max: 100

**Response Format:**
```json
{
  "data": [
    {
      "identity_arn": "arn:aws:iam::123456789012:user/alice",
      "identity_type": "IAMUser",
      "account_id": "123456789012",
      "last_activity_timestamp": "2024-01-15T10:30:00.000Z"
    }
  ],
  "metadata": {
    "count": 1,
    "next_token": "base64_encoded_last_key",
    "query_time_ms": 45
  }
}
```

**Error Response Format:**
```json
{
  "error": {
    "code": "InvalidParameter",
    "message": "Invalid identity_type value. Must be one of: IAMUser, AssumedRole, AWSService",
    "request_id": "abc123-def456"
  }
}
```

**Pagination Implementation:**
```python
# Encode LastEvaluatedKey as base64 next_token
# Decode next_token to ExclusiveStartKey for next query
# Return next_token in metadata if more results available
```

**Validation Rules:**
- limit: 1-100 (default: 25)
- identity_type: IAMUser | AssumedRole | AWSService
- status: open | investigating | resolved | false_positive
- severity: Low | Moderate | High | Very High | Critical
- date formats: ISO 8601 (YYYY-MM-DDTHH:MM:SSZ)

**Environment Variables:**
- `IDENTITY_PROFILE_TABLE`: DynamoDB table name
- `BLAST_RADIUS_SCORE_TABLE`: DynamoDB table name
- `INCIDENT_TABLE`: DynamoDB table name
- `EVENT_SUMMARY_TABLE`: DynamoDB table name
- `TRUST_RELATIONSHIP_TABLE`: DynamoDB table name
- `AWS_REGION`: AWS region

**IAM Permissions:**
- `dynamodb:Query`, `dynamodb:GetItem` on all tables
- `dynamodb:UpdateItem` on Incident table (for PATCH /incidents/{id})
- `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents`

**Logging:**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "correlation_id": "abc123-def456",
  "function": "api_handler",
  "method": "GET",
  "path": "/identities",
  "query_params": {"identity_type": "IAMUser"},
  "response_code": 200,
  "response_time_ms": 45,
  "result_count": 15
}
```

### Lambda Common Configuration

**Runtime:** Python 3.11

**Architecture:** arm64 (Graviton2 for cost savings)

**VPC Configuration:** None (all functions access public AWS services)

**Reserved Concurrency:**
- Dev: 10 per function (cost control)
- Prod: 100 per function (high availability)

**Dead Letter Queue:** SQS queue per function for failed invocations

**Environment Variables (Common):**
- `ENVIRONMENT`: dev | prod
- `LOG_LEVEL`: INFO | DEBUG
- `AWS_REGION`: AWS region

**Retry Configuration:**
- Asynchronous invocations: 2 retries with exponential backoff
- Synchronous invocations: No automatic retries (handled by caller)

**Timeout Strategy:**
- Event processing functions: 30-60s (allow time for retries)
- API functions: 10s (fast response for user experience)


## Event Flow Design

### CloudTrail to EventBridge Flow

```
CloudTrail Event → EventBridge → Event_Normalizer
                                       │
                                       ├─→ Event_Summary (DynamoDB)
                                       │
                                       ├─→ Detection_Engine (async)
                                       │        │
                                       │        └─→ Incident_Processor (async)
                                       │                 │
                                       │                 ├─→ Incident (DynamoDB)
                                       │                 └─→ SNS Alert (if high severity)
                                       │
                                       └─→ Identity_Collector (async)
                                                │
                                                ├─→ Identity_Profile (DynamoDB)
                                                └─→ Trust_Relationship (DynamoDB)
```

### Detailed Event Processing Steps

**Step 1: CloudTrail Capture**
- CloudTrail logs all management events across AWS Organization (prod) or single account (dev)
- Events delivered to EventBridge in near real-time (<1 minute latency)
- Events also stored in S3 for compliance and backup

**Step 2: EventBridge Filtering**
- EventBridge rule filters events by source: aws.iam, aws.sts, aws.organizations, aws.ec2
- Only management events (control plane) are processed, not data events
- Filtered events routed to Event_Normalizer Lambda

**EventBridge Rule Pattern:**
```json
{
  "source": ["aws.iam", "aws.sts", "aws.organizations", "aws.ec2"],
  "detail-type": ["AWS API Call via CloudTrail"],
  "detail": {
    "eventType": ["AwsApiCall"],
    "managementEvent": [true]
  }
}
```

**Step 3: Event Normalization**
- Event_Normalizer receives CloudTrail event from EventBridge
- Validates required fields (eventName, userIdentity, eventTime)
- Extracts identity ARN, event type, timestamp, source IP, user agent
- Parses event-specific parameters (resource ARNs, actions)
- Excludes sensitive data and large payloads
- Stores Event_Summary in DynamoDB
- Invokes Detection_Engine asynchronously with Event_Summary
- Invokes Identity_Collector asynchronously with Event_Summary

**Step 4: Detection Processing (Placeholder)**
- Detection_Engine receives Event_Summary from Event_Normalizer
- Logs event details for verification
- In Phase 2: No actual detection logic, just logging
- Forwards placeholder Finding to Incident_Processor for pipeline testing

**Step 5: Incident Creation (Placeholder Findings)**
- Incident_Processor receives placeholder Finding from Detection_Engine
- Checks for duplicate incidents (same identity + detection type within 24 hours)
- Creates new Incident or updates existing incident
- Stores Incident in DynamoDB with status "open"
- If severity is High/Very High/Critical, publishes to SNS Alert_Topic
- **Phase 2 Note:** Incidents are based on placeholder findings for pipeline testing, not real detections

**Step 6: Identity Profile Updates**
- Identity_Collector receives Event_Summary from Event_Normalizer
- Extracts identity metadata (ARN, type, account ID)
- Updates or creates Identity_Profile in DynamoDB
- Updates last_activity_timestamp and activity_count
- If AssumeRole event, creates Trust_Relationship record

**Step 7: Score Calculation (Placeholder)**
- Score_Engine runs on schedule (daily) or on-demand
- Queries Identity_Profile table for identities
- In Phase 2: Creates placeholder Blast_Radius_Score records (score: 50, severity: Moderate)
- Stores scores in DynamoDB

### Error Handling and Retry Logic

**Event_Normalizer Errors:**
- Missing required fields: Log error, skip event, continue
- DynamoDB write failure: Retry 3 times with exponential backoff (1s, 2s, 4s)
- Lambda invocation failure: Log error, send to DLQ
- Unhandled exceptions: Log with full context, send to DLQ

**Detection_Engine Errors:**
- Invalid input: Log error, return failure
- DynamoDB query failure: Retry 3 times with exponential backoff
- Lambda invocation failure: Log error, send to DLQ

**Incident_Processor Errors:**
- Missing required fields: Log error, return failure
- DynamoDB write failure: Retry 3 times with exponential backoff
- SNS publish failure: Log error but don't fail incident creation (alert is best-effort)
- Duplicate check failure: Create new incident (fail open to avoid missing incidents)

**Identity_Collector Errors:**
- ARN parsing failure: Log error, skip update
- DynamoDB write failure: Retry 3 times with exponential backoff
- Missing event fields: Log warning, continue with available data

**Dead Letter Queue Processing:**
- Failed events sent to SQS DLQ per Lambda function
- CloudWatch alarm triggers when DLQ message count > 0
- Manual investigation required for DLQ messages
- DLQ retention: 14 days

### Data Transformations

**CloudTrail Event → Event_Summary:**
```python
# Input: CloudTrail event from EventBridge
{
  "detail": {
    "eventID": "abc123",
    "eventName": "CreateUser",
    "eventTime": "2024-01-15T10:30:00Z",
    "userIdentity": {
      "type": "IAMUser",
      "arn": "arn:aws:iam::123456789012:user/admin"
    },
    "sourceIPAddress": "203.0.113.42",
    "userAgent": "aws-cli/2.13.0",
    "requestParameters": {"userName": "newuser"}
  }
}

# Output: Event_Summary
{
  "event_id": "abc123",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "event_type": "CreateUser",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "source_ip": "203.0.113.42",
  "user_agent": "aws-cli/2.13.0",
  "event_parameters": {
    "userName": "newuser"
  },
  "date_partition": "2024-01-15",
  "account_id": "123456789012",
  "region": "us-east-1"
}
```

**Event_Summary → Finding (Placeholder):**
```python
# In Phase 2, Detection_Engine just logs and forwards
# Future: Event_Summary → Detection Rules → Finding

# Placeholder Finding for pipeline testing
{
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "detection_type": "test_detection",
  "severity": "Low",
  "confidence": 50.0,
  "related_event_ids": ["abc123"],
  "evidence": {"placeholder": true},
  "timestamp": "2024-01-15T10:30:05.000Z"
}
```

**Finding → Incident:**
```python
# Input: Finding from Detection_Engine
{
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "detection_type": "privilege_escalation",
  "severity": "High",
  "confidence": 85.5,
  "related_event_ids": ["abc123", "def456"]
}

# Output: Incident
{
  "incident_id": "550e8400-e29b-41d4-a716-446655440000",
  "identity_arn": "arn:aws:iam::123456789012:user/admin",
  "detection_type": "privilege_escalation",
  "severity": "High",
  "confidence": 85.5,
  "status": "open",
  "creation_timestamp": "2024-01-15T10:30:05.000Z",
  "update_timestamp": "2024-01-15T10:30:05.000Z",
  "related_event_ids": ["abc123", "def456"],
  "status_history": [
    {"status": "open", "timestamp": "2024-01-15T10:30:05.000Z"}
  ]
}
```

### Correlation ID Strategy

**Purpose:** Trace requests across multiple Lambda functions and services.

**Implementation:**
- Use CloudTrail event_id as correlation_id
- Pass correlation_id in Lambda invocation payload
- Include correlation_id in all log entries
- Include correlation_id in SNS messages

**Log Correlation Example:**
```json
// Event_Normalizer log
{
  "correlation_id": "abc123-def456",
  "function": "event_normalizer",
  "message": "Event normalized"
}

// Detection_Engine log
{
  "correlation_id": "abc123-def456",
  "function": "detection_engine",
  "message": "Detection processing"
}

// Incident_Processor log
{
  "correlation_id": "abc123-def456",
  "function": "incident_processor",
  "message": "Incident created",
  "incident_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**CloudWatch Insights Query:**
```
fields @timestamp, function, message, incident_id
| filter correlation_id = "abc123-def456"
| sort @timestamp asc
```

### Throughput and Scaling

**Expected Event Volume:**
- Dev: ~100 events/hour (single account, limited activity)
- Prod: ~10,000 events/hour (organization-wide, multiple accounts)

**Lambda Concurrency:**
- Event_Normalizer: Up to 100 concurrent executions (prod)
- Detection_Engine: Up to 100 concurrent executions (prod)
- Incident_Processor: Up to 50 concurrent executions (prod)
- Identity_Collector: Up to 50 concurrent executions (prod)

**DynamoDB Throughput:**
- On-demand billing automatically scales with load
- No capacity planning required
- Cost scales linearly with usage

**EventBridge Limits:**
- 10,000 events/second per region (well above expected load)
- At-least-once delivery semantics (idempotency required)

## API Design

### REST Endpoint Specification

**Base URL:** `https://api.radius.example.com/v1`

**Authentication:** AWS IAM (SigV4)

**CORS Configuration:**
- Allowed Origins: `https://dashboard.radius.example.com` (configurable)
- Allowed Methods: GET, POST, PATCH, OPTIONS
- Allowed Headers: Authorization, Content-Type, X-Correlation-ID
- Max Age: 3600 seconds

### Endpoint Details

#### GET /identities

**Purpose:** List identity profiles with filtering and pagination.

**Query Parameters:**
- `identity_type` (optional): Filter by type (IAMUser | AssumedRole | AWSService)
- `account_id` (optional): Filter by AWS account ID
- `limit` (optional): Results per page (1-100, default: 25)
- `next_token` (optional): Pagination token from previous response

**Response (200 OK):**
```json
{
  "data": [
    {
      "identity_arn": "arn:aws:iam::123456789012:user/alice",
      "identity_type": "IAMUser",
      "account_id": "123456789012",
      "creation_date": "2023-06-15T08:00:00.000Z",
      "last_activity_timestamp": "2024-01-15T10:30:00.000Z",
      "tags": {"Environment": "Production"},
      "is_active": true,
      "activity_count": 1523
    }
  ],
  "metadata": {
    "count": 1,
    "next_token": "eyJpZGVudGl0eV9hcm4iOiAiYXJuOmF3czppYW0ifQ==",
    "query_time_ms": 45
  }
}
```

**Error Responses:**
- 400: Invalid parameter value
- 500: Internal server error

#### GET /identities/{arn}

**Purpose:** Retrieve a specific identity profile by ARN.

**Path Parameters:**
- `arn` (required): URL-encoded identity ARN

**Example:** `/identities/arn%3Aaws%3Aiam%3A%3A123456789012%3Auser%2Falice`

**Response (200 OK):**
```json
{
  "data": {
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "identity_type": "IAMUser",
    "account_id": "123456789012",
    "creation_date": "2023-06-15T08:00:00.000Z",
    "last_activity_timestamp": "2024-01-15T10:30:00.000Z",
    "tags": {"Environment": "Production"},
    "is_active": true,
    "activity_count": 1523
  },
  "metadata": {
    "query_time_ms": 12
  }
}
```

**Error Responses:**
- 400: Invalid ARN format
- 404: Identity not found
- 500: Internal server error

#### GET /scores

**Purpose:** List blast radius scores with filtering and pagination.

**Query Parameters:**
- `severity_level` (optional): Filter by severity (Low | Moderate | High | Very High | Critical)
- `min_score` (optional): Minimum score value (0-100)
- `max_score` (optional): Maximum score value (0-100)
- `limit` (optional): Results per page (1-100, default: 25)
- `next_token` (optional): Pagination token

**Response (200 OK):**
```json
{
  "data": [
    {
      "identity_arn": "arn:aws:iam::123456789012:user/alice",
      "score_value": 50,
      "severity_level": "Moderate",
      "calculation_timestamp": "2024-01-15T00:00:00.000Z",
      "contributing_factors": ["placeholder"],
      "previous_score": null,
      "score_change": 0
    }
  ],
  "metadata": {
    "count": 1,
    "next_token": null,
    "query_time_ms": 38
  }
}
```

**Phase 2 Note:** Scores shown are placeholder values (score: 50, severity: Moderate, factors: ["placeholder"]) for testing the API and data pipeline only. Actual scoring logic will be implemented in future phases.

#### GET /scores/{arn}

**Purpose:** Retrieve blast radius score for a specific identity.

**Path Parameters:**
- `arn` (required): URL-encoded identity ARN

**Response (200 OK):**
```json
{
  "data": {
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "score_value": 50,
    "severity_level": "Moderate",
    "calculation_timestamp": "2024-01-15T00:00:00.000Z",
    "contributing_factors": ["placeholder"],
    "previous_score": null,
    "score_change": 0
  },
  "metadata": {
    "query_time_ms": 15
  }
}
```

**Error Responses:**
- 404: Score not found for identity
- 500: Internal server error

#### GET /incidents

**Purpose:** List security incidents with filtering and pagination.

**Query Parameters:**
- `status` (optional): Filter by status (open | investigating | resolved | false_positive)
- `severity` (optional): Filter by severity (Low | Moderate | High | Very High | Critical)
- `identity_arn` (optional): Filter by identity ARN
- `start_date` (optional): Filter by creation date >= (ISO 8601)
- `end_date` (optional): Filter by creation date <= (ISO 8601)
- `limit` (optional): Results per page (1-100, default: 25)
- `next_token` (optional): Pagination token

**Response (200 OK):**
```json
{
  "data": [
    {
      "incident_id": "550e8400-e29b-41d4-a716-446655440000",
      "identity_arn": "arn:aws:iam::123456789012:user/alice",
      "detection_type": "privilege_escalation",
      "severity": "High",
      "confidence": 85.5,
      "status": "open",
      "creation_timestamp": "2024-01-15T10:30:05.000Z",
      "update_timestamp": "2024-01-15T10:30:05.000Z",
      "related_event_ids": ["abc123", "def456"],
      "notes": "",
      "assigned_to": ""
    }
  ],
  "metadata": {
    "count": 1,
    "next_token": null,
    "query_time_ms": 52
  }
}
```

#### GET /incidents/{id}

**Purpose:** Retrieve a specific incident by ID.

**Path Parameters:**
- `id` (required): Incident UUID

**Response (200 OK):**
```json
{
  "data": {
    "incident_id": "550e8400-e29b-41d4-a716-446655440000",
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "detection_type": "privilege_escalation",
    "severity": "High",
    "confidence": 85.5,
    "status": "open",
    "creation_timestamp": "2024-01-15T10:30:05.000Z",
    "update_timestamp": "2024-01-15T10:30:05.000Z",
    "related_event_ids": ["abc123", "def456"],
    "status_history": [
      {"status": "open", "timestamp": "2024-01-15T10:30:05.000Z"}
    ],
    "notes": "",
    "assigned_to": ""
  },
  "metadata": {
    "query_time_ms": 18
  }
}
```

**Error Responses:**
- 404: Incident not found
- 500: Internal server error

#### PATCH /incidents/{id}

**Purpose:** Update incident status and notes.

**Path Parameters:**
- `id` (required): Incident UUID

**Request Body:**
```json
{
  "status": "investigating",
  "notes": "Investigating privilege escalation pattern. Contacted user.",
  "assigned_to": "security-analyst@example.com"
}
```

**Response (200 OK):**
```json
{
  "data": {
    "incident_id": "550e8400-e29b-41d4-a716-446655440000",
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "detection_type": "privilege_escalation",
    "severity": "High",
    "confidence": 85.5,
    "status": "investigating",
    "creation_timestamp": "2024-01-15T10:30:05.000Z",
    "update_timestamp": "2024-01-15T11:45:22.000Z",
    "related_event_ids": ["abc123", "def456"],
    "status_history": [
      {"status": "open", "timestamp": "2024-01-15T10:30:05.000Z"},
      {"status": "investigating", "timestamp": "2024-01-15T11:45:22.000Z"}
    ],
    "notes": "Investigating privilege escalation pattern. Contacted user.",
    "assigned_to": "security-analyst@example.com"
  },
  "metadata": {
    "query_time_ms": 28
  }
}
```

**Error Responses:**
- 400: Invalid status value or request body
- 404: Incident not found
- 500: Internal server error

#### GET /events

**Purpose:** List normalized CloudTrail events with filtering and pagination.

**Query Parameters:**
- `identity_arn` (optional): Filter by identity ARN
- `event_type` (optional): Filter by event type (e.g., CreateUser, AssumeRole)
- `start_date` (optional): Filter by timestamp >= (ISO 8601)
- `end_date` (optional): Filter by timestamp <= (ISO 8601)
- `limit` (optional): Results per page (1-100, default: 25)
- `next_token` (optional): Pagination token

**Response (200 OK):**
```json
{
  "data": [
    {
      "event_id": "abc123-def456",
      "identity_arn": "arn:aws:iam::123456789012:user/alice",
      "event_type": "CreateUser",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "source_ip": "203.0.113.42",
      "user_agent": "aws-cli/2.13.0",
      "event_parameters": {
        "userName": "newuser"
      },
      "account_id": "123456789012",
      "region": "us-east-1"
    }
  ],
  "metadata": {
    "count": 1,
    "next_token": null,
    "query_time_ms": 67
  }
}
```

#### GET /events/{id}

**Purpose:** Retrieve a specific event by CloudTrail event ID.

**Path Parameters:**
- `id` (required): CloudTrail event ID

**Response (200 OK):**
```json
{
  "data": {
    "event_id": "abc123-def456",
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "event_type": "CreateUser",
    "timestamp": "2024-01-15T10:30:00.000Z",
    "source_ip": "203.0.113.42",
    "user_agent": "aws-cli/2.13.0",
    "event_parameters": {
      "userName": "newuser"
    },
    "date_partition": "2024-01-15",
    "account_id": "123456789012",
    "region": "us-east-1"
  },
  "metadata": {
    "query_time_ms": 22
  }
}
```

**Error Responses:**
- 404: Event not found
- 500: Internal server error

#### GET /trust-relationships

**Purpose:** List trust relationships with filtering and pagination.

**Query Parameters:**
- `source_arn` (optional): Filter by source identity ARN
- `target_account_id` (optional): Filter by target account ID
- `relationship_type` (optional): Filter by type (AssumeRole | ServicePrincipal | CrossAccount)
- `limit` (optional): Results per page (1-100, default: 25)
- `next_token` (optional): Pagination token

**Response (200 OK):**
```json
{
  "data": [
    {
      "source_arn": "arn:aws:iam::123456789012:user/alice",
      "target_arn": "arn:aws:iam::987654321098:role/CrossAccountRole",
      "relationship_type": "AssumeRole",
      "permissions_granted": ["sts:AssumeRole"],
      "discovery_timestamp": "2024-01-15T10:30:00.000Z",
      "last_used_timestamp": "2024-01-15T14:22:00.000Z",
      "is_active": true,
      "source_account_id": "123456789012",
      "target_account_id": "987654321098"
    }
  ],
  "metadata": {
    "count": 1,
    "next_token": null,
    "query_time_ms": 41
  }
}
```

### API Gateway Configuration

**API Type:** REST API (not HTTP API, for IAM authorization support)

**Authorization:** AWS_IAM

**Throttling:**
- Rate: 1000 requests/second
- Burst: 2000 requests

**Caching:** Disabled in Phase 2 (enable in future for performance)

**Request Validation:**
- Query parameter validation enabled
- Request body validation enabled for PATCH endpoints

**Logging:**
- Access logs: Enabled, sent to CloudWatch
- Execution logs: Enabled in dev, disabled in prod (verbose)
- Log format: JSON with request ID, method, path, status, latency

**Deployment Stages:**
- Dev: `dev` stage with detailed logging
- Prod: `prod` stage with access logs only

### Pagination Design

**Token-Based Pagination:**
- Use DynamoDB LastEvaluatedKey as pagination token
- Encode LastEvaluatedKey as base64 string
- Return as `next_token` in response metadata
- Client passes `next_token` as query parameter for next page

**Implementation:**
```python
# Encode pagination token
import base64
import json

def encode_pagination_token(last_evaluated_key):
    if not last_evaluated_key:
        return None
    return base64.b64encode(json.dumps(last_evaluated_key).encode()).decode()

def decode_pagination_token(next_token):
    if not next_token:
        return None
    return json.loads(base64.b64decode(next_token).decode())

# DynamoDB query with pagination
response = table.query(
    KeyConditionExpression=...,
    Limit=limit,
    ExclusiveStartKey=decode_pagination_token(next_token)
)

return {
    "data": response["Items"],
    "metadata": {
        "count": len(response["Items"]),
        "next_token": encode_pagination_token(response.get("LastEvaluatedKey"))
    }
}
```

**Pagination Limits:**
- Default limit: 25 items
- Maximum limit: 100 items
- Minimum limit: 1 item

### URL Encoding for ARN Parameters

**Problem:** ARNs contain special characters (`:`, `/`) that must be URL-encoded in path parameters.

**Example:**
- Original ARN: `arn:aws:iam::123456789012:user/alice`
- URL-encoded: `arn%3Aaws%3Aiam%3A%3A123456789012%3Auser%2Falice`

**Client Implementation:**
```javascript
// JavaScript example
const arn = "arn:aws:iam::123456789012:user/alice";
const encodedArn = encodeURIComponent(arn);
const url = `https://api.radius.example.com/v1/identities/${encodedArn}`;
```

**Lambda Handler:**
```python
# Python example
import urllib.parse

def handler(event, context):
    encoded_arn = event["pathParameters"]["arn"]
    arn = urllib.parse.unquote(encoded_arn)
    # Use decoded ARN for DynamoDB query
```


## Observability Design

### CloudWatch Log Groups

**Log Group Structure:**
- `/aws/lambda/radius-{env}-event-normalizer`
- `/aws/lambda/radius-{env}-detection-engine`
- `/aws/lambda/radius-{env}-incident-processor`
- `/aws/lambda/radius-{env}-identity-collector`
- `/aws/lambda/radius-{env}-score-engine`
- `/aws/lambda/radius-{env}-api-handler`
- `/aws/apigateway/radius-{env}-api`

**Log Retention:**
- Dev: 7 days
- Prod: 30 days

**Structured Logging Format:**
```json
{
  "timestamp": "2024-01-15T10:30:00.123Z",
  "level": "INFO",
  "correlation_id": "abc123-def456",
  "function": "event_normalizer",
  "message": "Event normalized successfully",
  "context": {
    "event_id": "abc123-def456",
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "event_type": "CreateUser"
  }
}
```

**Log Levels:**
- DEBUG: Detailed diagnostic information (dev only)
- INFO: General informational messages
- WARNING: Warning messages for recoverable issues
- ERROR: Error messages for failures requiring attention
- CRITICAL: Critical failures requiring immediate action


### CloudWatch Metrics

**Lambda Metrics (per function):**
- Invocations: Count of function invocations
- Errors: Count of function errors
- Duration: Execution time in milliseconds
- Throttles: Count of throttled invocations
- ConcurrentExecutions: Number of concurrent executions
- DeadLetterErrors: Count of DLQ delivery failures

**DynamoDB Metrics (per table):**
- ConsumedReadCapacityUnits: Read capacity consumed
- ConsumedWriteCapacityUnits: Write capacity consumed
- UserErrors: Count of 4xx errors
- SystemErrors: Count of 5xx errors
- ThrottledRequests: Count of throttled requests

**API Gateway Metrics:**
- Count: Total number of API requests
- 4XXError: Count of client errors
- 5XXError: Count of server errors
- Latency: Time between request and response
- IntegrationLatency: Time for backend to respond

**Custom Metrics:**
- EventsProcessed: Count of CloudTrail events processed
- IncidentsCreated: Count of incidents created
- AlertsSent: Count of SNS alerts sent
- IdentitiesUpdated: Count of identity profile updates


### CloudWatch Alarms

**Lambda Error Rate Alarms:**
- Metric: Errors / Invocations
- Threshold: > 5% over 5 minutes
- Evaluation periods: 2 consecutive periods
- Action: Publish to SNS operational topic

**Lambda Duration Alarms:**
- Metric: Duration
- Threshold: > 80% of timeout value
- Evaluation periods: 3 consecutive periods
- Action: Publish to SNS operational topic

**DynamoDB Throttle Alarms:**
- Metric: ThrottledRequests
- Threshold: > 10 per minute
- Evaluation periods: 2 consecutive periods
- Action: Publish to SNS operational topic

**Dead Letter Queue Alarms:**
- Metric: ApproximateNumberOfMessagesVisible
- Threshold: > 0
- Evaluation periods: 1 period
- Action: Publish to SNS operational topic (immediate)

**API Gateway Error Rate Alarms:**
- Metric: 5XXError / Count
- Threshold: > 1% over 5 minutes
- Evaluation periods: 2 consecutive periods
- Action: Publish to SNS operational topic


### CloudWatch Dashboards

**System Overview Dashboard:**
- Event processing rate (events/minute)
- Lambda invocation counts (all functions)
- Lambda error rates (all functions)
- DynamoDB read/write capacity consumed
- API Gateway request count and latency
- Active incidents by severity
- Dead letter queue message counts

**Lambda Performance Dashboard:**
- Duration percentiles (p50, p95, p99) per function
- Concurrent executions per function
- Error counts and types per function
- Throttle counts per function
- Memory utilization per function

**DynamoDB Performance Dashboard:**
- Read/write capacity consumed per table
- Throttled requests per table
- Item counts per table (estimated)
- GSI query performance
- Table size in bytes

**Incident Tracking Dashboard:**
- Incidents created (last 24 hours)
- Incidents by severity (pie chart)
- Incidents by status (bar chart)
- Mean time to resolution
- Alert delivery success rate


### CloudWatch Insights Queries

**Query 1: Error Analysis**
```
fields @timestamp, function, level, message, context.error_type
| filter level = "ERROR"
| stats count() by function, context.error_type
| sort count desc
```

**Query 2: Request Tracing**
```
fields @timestamp, function, message, context
| filter correlation_id = "{correlation_id}"
| sort @timestamp asc
```

**Query 3: Performance Analysis**
```
fields @timestamp, function, @duration
| filter function = "event_normalizer"
| stats avg(@duration), max(@duration), pct(@duration, 95) by bin(5m)
```

**Query 4: Incident Creation Rate**
```
fields @timestamp, message, context.incident_id, context.severity
| filter function = "incident_processor" and message = "Incident created"
| stats count() by context.severity, bin(1h)
```


## Dev vs Prod Differences

### CloudTrail Configuration

**Dev:**
- Single-account trail
- Captures events from dev AWS account only
- Lower event volume (~100 events/hour)
- Simplified testing and debugging

**Prod:**
- Organization-wide trail
- Captures events from all accounts in AWS Organization
- High event volume (~10,000 events/hour)
- Comprehensive security coverage

### Resource Configuration

**Dev:**
- Lambda memory: 50% of prod values
- Lambda concurrency: 10 per function
- Log retention: 7 days
- DynamoDB PITR: Disabled for Event_Summary and Trust_Relationship
- CloudWatch alarm thresholds: Relaxed (higher error tolerance)
- API Gateway throttling: 100 requests/second

**Prod:**
- Lambda memory: Full allocation for performance
- Lambda concurrency: 100 per function
- Log retention: 30 days
- DynamoDB PITR: Enabled for all critical tables
- CloudWatch alarm thresholds: Strict (low error tolerance)
- API Gateway throttling: 1000 requests/second


### Cost Optimization

**Dev Cost Strategies:**
- Lower Lambda memory and concurrency limits
- Shorter log retention periods
- Disabled PITR for high-volume tables
- Single-account CloudTrail (lower event volume)
- Relaxed alarm thresholds (fewer false positives)
- On-demand DynamoDB billing (no reserved capacity)

**Prod Cost Strategies:**
- Right-sized Lambda memory (not over-provisioned)
- On-demand DynamoDB billing (scales with actual usage)
- S3 lifecycle policies for CloudTrail logs (archive to Glacier after 90 days)
- Event_Summary TTL (automatic deletion after 90 days)
- Incident TTL (archive resolved incidents after 90 days)
- ARM64 Lambda architecture (20% cost savings vs x86)

**Estimated Monthly Costs:**
- Dev: $50-100 (minimal usage, cost controls)
- Prod: $500-1000 (organization-wide, high availability)

### Feature Flags

**Dev-Only Features:**
- Sample event injection via scripts/inject-events.py
- Detailed execution logs (DEBUG level)
- Relaxed validation rules
- Test data seeding

**Prod-Only Features:**
- Organization-wide CloudTrail
- High availability configuration
- Strict alarm thresholds
- Cross-region backup (future)


## Deployment Design

### Terraform Deployment Workflow

**Step 1: Initialize Backend**
```bash
cd infra/envs/dev
terraform init -backend-config=backend.tfvars
```

**Step 2: Plan Changes**
```bash
terraform plan -var-file=terraform.tfvars -out=tfplan
```

**Step 3: Review Plan**
- Review resource changes
- Verify no unexpected deletions
- Check resource dependencies

**Step 4: Apply Changes**
```bash
terraform apply tfplan
```

**Step 5: Verify Deployment**
- Check Lambda functions are created
- Verify DynamoDB tables exist with GSIs
- Test API Gateway endpoint
- Verify EventBridge rules are active

### Lambda Code Packaging

**Build Process:**
1. Install Python dependencies in `backend/` directory
2. Create deployment package (zip file) per Lambda function
3. Include function code and dependencies
4. Upload to S3 deployment bucket
5. Reference S3 object in Terraform Lambda resource

**Directory Structure:**
```
backend/
├── event_normalizer/
│   ├── handler.py          # Lambda entry point
│   └── requirements.txt    # Function dependencies
├── detection_engine/
│   ├── handler.py
│   └── requirements.txt
├── incident_processor/
│   ├── handler.py
│   └── requirements.txt
├── identity_collector/
│   ├── handler.py
│   └── requirements.txt
├── score_engine/
│   ├── handler.py
│   └── requirements.txt
├── api_handler/
│   ├── handler.py
│   └── requirements.txt
└── shared/
    ├── __init__.py
    ├── logging_utils.py    # Structured logging
    ├── dynamodb_utils.py   # DynamoDB helpers
    └── validation.py       # Input validation
```


**Build Script (scripts/build-lambdas.sh):**
```bash
#!/bin/bash
set -e

BACKEND_DIR="backend"
BUILD_DIR="build"
DEPLOYMENT_BUCKET="radius-${ENVIRONMENT}-deployments"

# Create build directory
mkdir -p ${BUILD_DIR}

# Build each Lambda function
for function in event_normalizer detection_engine incident_processor identity_collector score_engine api_handler; do
  echo "Building ${function}..."
  
  # Create function build directory
  mkdir -p ${BUILD_DIR}/${function}
  
  # Copy function code
  cp -r ${BACKEND_DIR}/${function}/* ${BUILD_DIR}/${function}/
  
  # Copy shared utilities
  cp -r ${BACKEND_DIR}/shared ${BUILD_DIR}/${function}/
  
  # Install dependencies
  if [ -f ${BUILD_DIR}/${function}/requirements.txt ]; then
    pip install -r ${BUILD_DIR}/${function}/requirements.txt -t ${BUILD_DIR}/${function}/
  fi
  
  # Create deployment package
  cd ${BUILD_DIR}/${function}
  zip -r ../${function}.zip . -x "*.pyc" "__pycache__/*"
  cd ../..
  
  # Upload to S3
  aws s3 cp ${BUILD_DIR}/${function}.zip s3://${DEPLOYMENT_BUCKET}/lambdas/${function}.zip
  
  echo "Built ${function}.zip"
done

echo "All Lambda functions built successfully"
```


### Environment Variable Injection

**Terraform Configuration:**
```hcl
resource "aws_lambda_function" "event_normalizer" {
  function_name = "${var.prefix}-event-normalizer"
  s3_bucket     = aws_s3_bucket.deployments.id
  s3_key        = "lambdas/event_normalizer.zip"
  handler       = "handler.lambda_handler"
  runtime       = "python3.11"
  
  environment {
    variables = {
      ENVIRONMENT              = var.environment
      LOG_LEVEL               = var.log_level
      EVENT_SUMMARY_TABLE     = aws_dynamodb_table.event_summary.name
      DETECTION_ENGINE_ARN    = aws_lambda_function.detection_engine.arn
      IDENTITY_COLLECTOR_ARN  = aws_lambda_function.identity_collector.arn
      AWS_REGION              = var.aws_region
    }
  }
}
```

**Lambda Handler Access:**
```python
import os

EVENT_SUMMARY_TABLE = os.environ['EVENT_SUMMARY_TABLE']
DETECTION_ENGINE_ARN = os.environ['DETECTION_ENGINE_ARN']
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
```

### Seeding Test Data in Dev

**Test Data Seeding Script (scripts/seed-dev-data.py):**
```python
#!/usr/bin/env python3
import boto3
import json
from datetime import datetime, timedelta

dynamodb = boto3.resource('dynamodb')

def seed_identity_profiles():
    table = dynamodb.Table('radius-dev-identity-profile')
    
    identities = [
        {
            'identity_arn': 'arn:aws:iam::123456789012:user/alice',
            'identity_type': 'IAMUser',
            'account_id': '123456789012',
            'creation_date': '2023-01-15T00:00:00.000Z',
            'last_activity_timestamp': datetime.utcnow().isoformat() + 'Z',
            'is_active': True,
            'activity_count': 150
        },
        # More test identities...
    ]
    
    for identity in identities:
        table.put_item(Item=identity)
    
    print(f"Seeded {len(identities)} identity profiles")

def seed_blast_radius_scores():
    table = dynamodb.Table('radius-dev-blast-radius-score')
    
    scores = [
        {
            'identity_arn': 'arn:aws:iam::123456789012:user/alice',
            'score_value': 75,
            'severity_level': 'Very High',
            'calculation_timestamp': datetime.utcnow().isoformat() + 'Z',
            'contributing_factors': ['placeholder']
        },
        # More test scores...
    ]
    
    for score in scores:
        table.put_item(Item=score)
    
    print(f"Seeded {len(scores)} blast radius scores")

if __name__ == '__main__':
    seed_identity_profiles()
    seed_blast_radius_scores()
    print("Dev data seeding complete")
```


### Deployment Scripts

**Main Deployment Script (scripts/deploy.sh):**
```bash
#!/bin/bash
set -e

ENVIRONMENT=$1

if [ -z "$ENVIRONMENT" ]; then
  echo "Usage: ./deploy.sh [dev|prod]"
  exit 1
fi

echo "Deploying Radius to ${ENVIRONMENT} environment..."

# Step 1: Build Lambda functions
echo "Building Lambda functions..."
./scripts/build-lambdas.sh

# Step 2: Deploy infrastructure
echo "Deploying infrastructure with Terraform..."
cd infra/envs/${ENVIRONMENT}
terraform init -backend-config=backend.tfvars
terraform plan -var-file=terraform.tfvars -out=tfplan
terraform apply tfplan

# Step 3: Seed test data (dev only)
if [ "$ENVIRONMENT" = "dev" ]; then
  echo "Seeding test data..."
  cd ../../..
  python3 scripts/seed-dev-data.py
fi

echo "Deployment complete!"
echo "API Endpoint: $(terraform output -raw api_endpoint)"
```

**Verification Script (scripts/verify-deployment.sh):**
```bash
#!/bin/bash
set -e

ENVIRONMENT=$1
API_ENDPOINT=$(cd infra/envs/${ENVIRONMENT} && terraform output -raw api_endpoint)

echo "Verifying deployment for ${ENVIRONMENT}..."

# Check Lambda functions
echo "Checking Lambda functions..."
for function in event-normalizer detection-engine incident-processor identity-collector score-engine api-handler; do
  aws lambda get-function --function-name radius-${ENVIRONMENT}-${function} > /dev/null
  echo "✓ ${function} exists"
done

# Check DynamoDB tables
echo "Checking DynamoDB tables..."
for table in identity-profile blast-radius-score incident event-summary trust-relationship; do
  aws dynamodb describe-table --table-name radius-${ENVIRONMENT}-${table} > /dev/null
  echo "✓ ${table} exists"
done

# Check API Gateway
echo "Checking API Gateway..."
curl -s -o /dev/null -w "%{http_code}" ${API_ENDPOINT}/identities?limit=1
echo "✓ API Gateway responding"

echo "Deployment verification complete!"
```


### State Management

**S3 State Bucket Configuration:**
```hcl
resource "aws_s3_bucket" "terraform_state" {
  bucket = "radius-terraform-state-${data.aws_caller_identity.current.account_id}"
  
  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.terraform_state.arn
    }
  }
}
```

**DynamoDB Lock Table:**
```hcl
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "radius-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"
  
  attribute {
    name = "LockID"
    type = "S"
  }
}
```

**Backend Configuration (infra/envs/dev/backend.tfvars):**
```hcl
bucket         = "radius-terraform-state-123456789012"
key            = "dev/terraform.tfstate"
region         = "us-east-1"
encrypt        = true
kms_key_id     = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
dynamodb_table = "radius-terraform-locks"
```


## Backend Package Structure

### Directory Layout

```
backend/
├── event_normalizer/
│   ├── handler.py              # Lambda entry point
│   ├── normalizer.py           # Event normalization logic
│   ├── requirements.txt        # boto3, python-dateutil
│   └── tests/
│       ├── test_handler.py
│       └── test_normalizer.py
├── detection_engine/
│   ├── handler.py              # Lambda entry point
│   ├── engine.py               # Detection engine placeholder
│   ├── interfaces.py           # Detection rule interfaces
│   ├── requirements.txt        # boto3
│   └── tests/
│       ├── test_handler.py
│       └── test_interfaces.py
├── incident_processor/
│   ├── handler.py              # Lambda entry point
│   ├── processor.py            # Incident creation logic
│   ├── deduplication.py        # Duplicate detection
│   ├── requirements.txt        # boto3
│   └── tests/
│       ├── test_handler.py
│       ├── test_processor.py
│       └── test_deduplication.py
├── identity_collector/
│   ├── handler.py              # Lambda entry point
│   ├── collector.py            # Identity profile updates
│   ├── arn_parser.py           # ARN parsing utilities
│   ├── requirements.txt        # boto3
│   └── tests/
│       ├── test_handler.py
│       ├── test_collector.py
│       └── test_arn_parser.py
├── score_engine/
│   ├── handler.py              # Lambda entry point
│   ├── engine.py               # Score engine placeholder
│   ├── interfaces.py           # Scoring rule interfaces
│   ├── severity.py             # Severity classification
│   ├── requirements.txt        # boto3
│   └── tests/
│       ├── test_handler.py
│       ├── test_interfaces.py
│       └── test_severity.py
├── api_handler/
│   ├── handler.py              # Lambda entry point
│   ├── endpoints.py            # Endpoint routing
│   ├── pagination.py           # Pagination utilities
│   ├── requirements.txt        # boto3
│   └── tests/
│       ├── test_handler.py
│       ├── test_endpoints.py
│       └── test_pagination.py
└── shared/
    ├── __init__.py
    ├── logging_utils.py        # Structured logging setup
    ├── dynamodb_utils.py       # DynamoDB query helpers
    ├── validation.py           # Input validation
    ├── errors.py               # Custom exception classes
    └── tests/
        ├── test_logging_utils.py
        ├── test_dynamodb_utils.py
        └── test_validation.py
```


### Shared Utilities

**logging_utils.py:**
```python
import json
import logging
import os
from datetime import datetime

def setup_logger(function_name):
    """Configure structured JSON logging."""
    logger = logging.getLogger()
    logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))
    
    # Remove default handlers
    for handler in logger.handlers:
        logger.removeHandler(handler)
    
    # Add JSON formatter
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(function_name))
    logger.addHandler(handler)
    
    return logger

class JsonFormatter(logging.Formatter):
    def __init__(self, function_name):
        self.function_name = function_name
        super().__init__()
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'function': self.function_name,
            'message': record.getMessage(),
        }
        
        # Add correlation_id if present
        if hasattr(record, 'correlation_id'):
            log_data['correlation_id'] = record.correlation_id
        
        # Add context if present
        if hasattr(record, 'context'):
            log_data['context'] = record.context
        
        return json.dumps(log_data)
```

**dynamodb_utils.py:**
```python
import boto3
from boto3.dynamodb.conditions import Key, Attr

dynamodb = boto3.resource('dynamodb')

def query_table(table_name, key_condition, index_name=None, limit=25, exclusive_start_key=None):
    """Query DynamoDB table with pagination support."""
    table = dynamodb.Table(table_name)
    
    query_params = {
        'KeyConditionExpression': key_condition,
        'Limit': limit
    }
    
    if index_name:
        query_params['IndexName'] = index_name
    
    if exclusive_start_key:
        query_params['ExclusiveStartKey'] = exclusive_start_key
    
    response = table.query(**query_params)
    
    return {
        'items': response.get('Items', []),
        'last_evaluated_key': response.get('LastEvaluatedKey')
    }

def get_item(table_name, key):
    """Get single item from DynamoDB table."""
    table = dynamodb.Table(table_name)
    response = table.get_item(Key=key)
    return response.get('Item')

def put_item(table_name, item):
    """Put item into DynamoDB table."""
    table = dynamodb.Table(table_name)
    table.put_item(Item=item)

def update_item(table_name, key, update_expression, expression_values):
    """Update item in DynamoDB table."""
    table = dynamodb.Table(table_name)
    table.update_item(
        Key=key,
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_values
    )
```


**validation.py:**
```python
from typing import Any, Dict, List, Optional
import re

class ValidationError(Exception):
    """Raised when validation fails."""
    pass

def validate_arn(arn: str) -> bool:
    """Validate AWS ARN format."""
    arn_pattern = r'^arn:aws:[a-z0-9\-]+:[a-z0-9\-]*:\d{12}:.+$'
    return bool(re.match(arn_pattern, arn))

def validate_severity(severity: str) -> bool:
    """Validate severity level."""
    valid_severities = ['Low', 'Moderate', 'High', 'Very High', 'Critical']
    return severity in valid_severities

def validate_status(status: str) -> bool:
    """Validate incident status."""
    valid_statuses = ['open', 'investigating', 'resolved', 'false_positive']
    return status in valid_statuses

def validate_identity_type(identity_type: str) -> bool:
    """Validate identity type."""
    valid_types = ['IAMUser', 'AssumedRole', 'AWSService']
    return identity_type in valid_types

def validate_pagination_params(limit: Optional[int], next_token: Optional[str]) -> Dict[str, Any]:
    """Validate and normalize pagination parameters."""
    if limit is not None:
        if not isinstance(limit, int) or limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
    else:
        limit = 25  # Default
    
    return {
        'limit': limit,
        'next_token': next_token
    }
```

**errors.py:**
```python
class RadiusError(Exception):
    """Base exception for Radius errors."""
    pass

class ValidationError(RadiusError):
    """Raised when input validation fails."""
    pass

class NotFoundError(RadiusError):
    """Raised when requested resource is not found."""
    pass

class DuplicateError(RadiusError):
    """Raised when attempting to create duplicate resource."""
    pass

class ExternalServiceError(RadiusError):
    """Raised when external service (DynamoDB, Lambda) fails."""
    pass
```


### Lambda Handler Entry Points

**Example: event_normalizer/handler.py**
```python
import json
import os
from shared.logging_utils import setup_logger
from shared.dynamodb_utils import put_item
from shared.errors import ValidationError
from normalizer import normalize_event

logger = setup_logger('event_normalizer')

def lambda_handler(event, context):
    """
    Lambda handler for Event Normalizer.
    Receives CloudTrail events from EventBridge.
    """
    try:
        # Extract CloudTrail event from EventBridge wrapper
        cloudtrail_event = event.get('detail', {})
        
        # Extract correlation ID
        correlation_id = cloudtrail_event.get('eventID', context.request_id)
        
        logger.info(
            'Processing CloudTrail event',
            extra={
                'correlation_id': correlation_id,
                'context': {
                    'event_type': cloudtrail_event.get('eventName'),
                    'event_id': correlation_id
                }
            }
        )
        
        # Normalize event
        event_summary = normalize_event(cloudtrail_event)
        
        # Store in DynamoDB
        table_name = os.environ['EVENT_SUMMARY_TABLE']
        put_item(table_name, event_summary)
        
        # Invoke downstream functions
        invoke_detection_engine(event_summary, correlation_id)
        invoke_identity_collector(event_summary, correlation_id)
        
        logger.info(
            'Event normalized successfully',
            extra={
                'correlation_id': correlation_id,
                'context': {
                    'event_id': event_summary['event_id'],
                    'identity_arn': event_summary['identity_arn']
                }
            }
        )
        
        return {'statusCode': 200, 'body': 'Success'}
        
    except ValidationError as e:
        logger.error(
            'Validation error',
            extra={
                'correlation_id': correlation_id,
                'context': {'error': str(e)}
            }
        )
        return {'statusCode': 400, 'body': str(e)}
        
    except Exception as e:
        logger.error(
            'Unexpected error',
            extra={
                'correlation_id': correlation_id,
                'context': {
                    'error_type': type(e).__name__,
                    'error_message': str(e)
                }
            }
        )
        raise
```


### Testing Structure

**Unit Tests:**
- Test individual functions and modules
- Mock external dependencies (DynamoDB, Lambda)
- Focus on business logic correctness
- Run locally without AWS credentials

**Integration Tests:**
- Test Lambda functions end-to-end
- Use LocalStack or AWS dev environment
- Test DynamoDB interactions
- Test Lambda invocations

**Property-Based Tests:**
- Test universal properties across many inputs
- Use Hypothesis library for Python
- Minimum 100 iterations per test
- Tag tests with design document property references

**Test Configuration (pytest.ini):**
```ini
[pytest]
testpaths = backend
python_files = test_*.py
python_classes = Test*
python_functions = test_*
markers =
    unit: Unit tests (fast, no external dependencies)
    integration: Integration tests (require AWS or LocalStack)
    property: Property-based tests (comprehensive input coverage)
```

**Example Unit Test:**
```python
# backend/event_normalizer/tests/test_normalizer.py
import pytest
from normalizer import normalize_event, extract_identity_arn

def test_extract_identity_arn_from_iam_user():
    """Test ARN extraction for IAM user."""
    user_identity = {
        'type': 'IAMUser',
        'arn': 'arn:aws:iam::123456789012:user/alice'
    }
    
    arn = extract_identity_arn(user_identity)
    
    assert arn == 'arn:aws:iam::123456789012:user/alice'

def test_normalize_event_creates_event_summary():
    """Test event normalization creates valid Event_Summary."""
    cloudtrail_event = {
        'eventID': 'abc123',
        'eventName': 'CreateUser',
        'eventTime': '2024-01-15T10:30:00Z',
        'userIdentity': {
            'type': 'IAMUser',
            'arn': 'arn:aws:iam::123456789012:user/admin'
        },
        'sourceIPAddress': '203.0.113.42',
        'userAgent': 'aws-cli/2.13.0'
    }
    
    event_summary = normalize_event(cloudtrail_event)
    
    assert event_summary['event_id'] == 'abc123'
    assert event_summary['identity_arn'] == 'arn:aws:iam::123456789012:user/admin'
    assert event_summary['event_type'] == 'CreateUser'
    assert 'timestamp' in event_summary
    assert 'date_partition' in event_summary
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property Reflection

After analyzing all acceptance criteria, I identified the following redundancies and consolidations:

**Redundancy Analysis:**

1. **Event Normalization Properties (6.1, 6.2, 6.5, 6.6)**: These can be consolidated into a single comprehensive property about field extraction and normalization
2. **API Query Properties (9.1-9.10)**: These are all variations of "query the correct table/GSI based on parameters" and can be consolidated
3. **Validation Properties (6.3, 8.1, 9.11)**: All Lambda functions validate inputs - can be consolidated into a general validation property
4. **Error Logging Properties (3.17, 6.10, 9.18)**: All Lambda functions log errors with structured format - can be consolidated
5. **Identity ARN Parsing (8.11, 8.12)**: Both extract information from ARNs - can be consolidated into one ARN parsing property

**Consolidated Properties:**

After reflection, the following properties provide unique validation value without redundancy:


### Property 1: Event Normalization Round-Trip

*For any* valid CloudTrail event, normalizing the event to Event_Summary format, then serializing it, then normalizing again should produce an equivalent Event_Summary structure with all required fields preserved (event_id, identity_arn, event_type, timestamp, source_ip, user_agent, event_parameters, date_partition, account_id, region).

**Validates: Requirements 6.11**

**Rationale:** This round-trip property ensures the normalization process is consistent and doesn't lose information. It's the most comprehensive test of the Event_Normalizer's correctness.

### Property 2: Required Field Validation

*For any* Lambda function that receives external input (Event_Normalizer, Incident_Processor, API_Handler), when required fields are missing from the input, the function should reject the input with a validation error and log the error with the correlation ID.

**Validates: Requirements 6.3, 6.4, 8.1, 9.11, 9.16**

**Rationale:** All input validation follows the same pattern - validate required fields, reject invalid input, log errors. This property ensures consistent validation behavior across all functions.

### Property 3: Structured Error Logging

*For any* Lambda function, when an error occurs (validation error, DynamoDB error, or unexpected exception), the function should log a structured JSON message containing timestamp, level, correlation_id, function name, message, and error context.

**Validates: Requirements 3.17, 6.10, 9.18**

**Rationale:** Consistent structured logging is critical for observability and troubleshooting across all Lambda functions.

### Property 4: Retry with Exponential Backoff

*For any* Lambda function that encounters a transient error (DynamoDB throttling, temporary network failure), the function should retry the operation with exponential backoff (1s, 2s, 4s) for up to 3 attempts before failing.

**Validates: Requirements 3.18**

**Rationale:** Consistent retry behavior ensures resilience across all Lambda functions when dealing with transient failures.

### Property 5: Dead Letter Queue on Exhausted Retries

*For any* event-driven Lambda function (Event_Normalizer, Detection_Engine, Incident_Processor, Identity_Collector), when all retry attempts are exhausted, the failed event should be sent to the function's dead letter queue.

**Validates: Requirements 3.19**

**Rationale:** Ensures no events are silently dropped when processing fails permanently.


### Property 6: Event Storage and Forwarding

*For any* valid CloudTrail event processed by Event_Normalizer, the normalized Event_Summary should be stored in DynamoDB AND forwarded to Detection_Engine AND (if identity-related) forwarded to Identity_Collector.

**Validates: Requirements 6.8, 6.9**

**Rationale:** Ensures the event processing pipeline is complete - events are both persisted and forwarded to downstream processors.

### Property 7: Timestamp Normalization to ISO 8601

*For any* CloudTrail event with a timestamp in any valid format, the Event_Normalizer should convert it to ISO 8601 format (YYYY-MM-DDTHH:MM:SS.sssZ) in the Event_Summary.

**Validates: Requirements 6.5**

**Rationale:** Consistent timestamp format is critical for time-based queries and sorting across all events.

### Property 8: Identity ARN Parsing

*For any* valid AWS identity ARN (IAM user, assumed role, or service), the Identity_Collector should correctly extract the identity_type (IAMUser, AssumedRole, AWSService) and account_id from the ARN structure.

**Validates: Requirements 8.11, 8.12**

**Rationale:** Correct ARN parsing is fundamental to identity tracking and ensures data consistency across the system.

### Property 9: Incident ID Uniqueness

*For any* set of incidents created by Incident_Processor, all incident IDs should be unique and conform to UUID v4 format.

**Validates: Requirements 8.2**

**Rationale:** Unique incident IDs are critical for incident tracking and prevent data corruption from ID collisions.

### Property 10: Incident Deduplication

*For any* identity ARN and detection type, when multiple findings are received within a 24-hour window, the Incident_Processor should update the existing incident (appending event IDs) rather than creating duplicate incidents.

**Validates: Requirements 8.7**

**Rationale:** Prevents alert fatigue and ensures incidents represent distinct security events rather than repeated detections of the same issue.


### Property 11: High-Severity Incident Alerting

*For any* incident with severity level of High, Very High, or Critical, the Incident_Processor should publish a notification to the SNS Alert_Topic containing incident_id, identity_arn, detection_type, severity, confidence, and dashboard_link.

**Validates: Requirements 8.4, 8.5**

**Rationale:** Ensures security teams are notified of critical incidents requiring immediate attention.

### Property 12: Incident Status Transitions

*For any* incident, status transitions should follow valid state machine rules: open → investigating, open → false_positive, investigating → resolved, and each transition should append to status_history with timestamp.

**Validates: Requirements 8.8, 8.9**

**Rationale:** Ensures incident lifecycle is tracked correctly and status history provides audit trail.

### Property 13: Identity Profile Updates

*For any* identity-related CloudTrail event, the Identity_Collector should update the Identity_Profile's last_activity_timestamp to the event timestamp and increment the activity_count.

**Validates: Requirements 8.10, 8.13**

**Rationale:** Ensures identity profiles accurately reflect recent activity for risk assessment.

### Property 14: Trust Relationship Creation on AssumeRole

*For any* AssumeRole CloudTrail event, the Identity_Collector should create or update a Trust_Relationship record with source_arn (who assumed), target_arn (what was assumed), relationship_type "AssumeRole", and last_used_timestamp.

**Validates: Requirements 8.15**

**Rationale:** Ensures cross-account and role assumption relationships are tracked for blast radius analysis.

### Property 15: Identity Deletion Handling

*For any* identity deletion event (DeleteUser, DeleteRole), the Identity_Collector should mark the Identity_Profile as inactive (is_active = false) rather than deleting the record.

**Validates: Requirements 8.18**

**Rationale:** Preserves historical data for audit and analysis while indicating the identity no longer exists.


### Property 16: API Response Format Consistency

*For any* successful API request to any endpoint, the API_Handler should return a JSON response with structure {data: [...], metadata: {count, next_token, query_time_ms}} and HTTP status code 200.

**Validates: Requirements 9.14**

**Rationale:** Consistent response format across all endpoints simplifies client implementation and ensures predictable API behavior.

### Property 17: API Pagination Correctness

*For any* API query that returns more results than the limit, the API_Handler should return a next_token in metadata, and using that next_token in a subsequent request should return the next page of results without duplicates or gaps.

**Validates: Requirements 9.12**

**Rationale:** Correct pagination is critical for clients to retrieve complete result sets without missing or duplicate data.

### Property 18: API Result Limit Enforcement

*For any* API request with a limit parameter, the API_Handler should return at most that many items (maximum 100, default 25), regardless of how many items match the query.

**Validates: Requirements 9.13**

**Rationale:** Prevents excessive data transfer and ensures consistent API performance.

### Property 19: API Error Status Codes

*For any* API request, the API_Handler should return appropriate HTTP status codes: 200 for success, 400 for invalid parameters, 404 for resource not found, 500 for server errors.

**Validates: Requirements 9.15, 9.16, 9.17**

**Rationale:** Standard HTTP status codes enable proper error handling in client applications.

### Property 20: API Query Routing

*For any* API request with query parameters, the API_Handler should query the appropriate DynamoDB table and GSI based on the parameters provided (e.g., identity_type uses IdentityTypeIndex, status uses StatusIndex).

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.8, 9.9, 9.10**

**Rationale:** Efficient query routing ensures optimal DynamoDB performance and cost by using the correct indexes.


### Property 21: Score Severity Classification

*For any* score value between 0 and 100, the Score_Engine should classify it into the correct severity level: 0-19 = Low, 20-39 = Moderate, 40-59 = High, 60-79 = Very High, 80-100 = Critical.

**Validates: Requirements 7.12**

**Rationale:** Consistent severity classification enables filtering and alerting based on risk levels.

### Property 22: Placeholder Score Creation

*For any* identity ARN provided to Score_Engine in Phase 2, the engine should create a Blast_Radius_Score record with score_value = 50, severity_level = "Moderate", and contributing_factors = ["placeholder"].

**Validates: Requirements 7.10**

**Rationale:** Ensures the scoring pipeline and API endpoints can be tested even though actual scoring logic is not implemented in Phase 2.

### Property 23: Detection Engine Logging

*For any* Event_Summary received by Detection_Engine in Phase 2, the engine should log the event with event_id, identity_arn, and event_type, then forward to Incident_Processor for pipeline testing.

**Validates: Requirements 7.1, 7.4**

**Rationale:** Ensures the detection pipeline is functional and can be monitored, even though detection logic is not implemented in Phase 2.

### Property 24: Sensitive Data Exclusion

*For any* CloudTrail event containing fields with names matching sensitive patterns (password, secret, key, token) or payloads exceeding 10KB, the Event_Normalizer should exclude those fields from the Event_Summary.

**Validates: Requirements 6.7**

**Rationale:** Prevents storage of sensitive credentials and reduces DynamoDB storage costs for large payloads.


## Error Handling

### Error Categories

**Validation Errors:**
- Missing required fields in input
- Invalid field formats (ARN, timestamp, UUID)
- Out-of-range values (score, limit)
- Response: Log error, return 400 status (API) or skip event (event processing)

**Resource Not Found Errors:**
- Requested identity, incident, or event does not exist
- Response: Log warning, return 404 status (API only)

**External Service Errors:**
- DynamoDB throttling or service errors
- Lambda invocation failures
- SNS publish failures
- Response: Retry with exponential backoff, then send to DLQ if exhausted

**Unexpected Errors:**
- Unhandled exceptions
- Programming errors
- Response: Log full stack trace with correlation ID, send to DLQ, trigger alarm

### Error Response Format (API)

```json
{
  "error": {
    "code": "ValidationError",
    "message": "Invalid identity_type value. Must be one of: IAMUser, AssumedRole, AWSService",
    "request_id": "abc123-def456",
    "details": {
      "field": "identity_type",
      "provided_value": "InvalidType",
      "valid_values": ["IAMUser", "AssumedRole", "AWSService"]
    }
  }
}
```

### Retry Strategy

**Transient Errors (Retry):**
- DynamoDB throttling (ProvisionedThroughputExceededException)
- Network timeouts
- Service unavailable (503)

**Permanent Errors (No Retry):**
- Validation errors (400)
- Resource not found (404)
- Authorization errors (403)

**Retry Configuration:**
- Max attempts: 3
- Backoff: Exponential (1s, 2s, 4s)
- Jitter: ±20% to prevent thundering herd

### Dead Letter Queue Strategy

**DLQ per Lambda Function:**
- Each event-driven Lambda has dedicated SQS DLQ
- Failed events sent to DLQ after retry exhaustion
- DLQ retention: 14 days
- CloudWatch alarm triggers when DLQ message count > 0

**DLQ Message Format:**
```json
{
  "original_event": {...},
  "error_message": "DynamoDB throttling exceeded retry limit",
  "error_type": "ProvisionedThroughputExceededException",
  "retry_count": 3,
  "correlation_id": "abc123-def456",
  "timestamp": "2024-01-15T10:30:00.000Z"
}
```

**DLQ Processing:**
- Manual investigation required
- Replay capability via scripts/replay-dlq.py
- Root cause analysis to prevent recurrence


## Testing Strategy

### Dual Testing Approach

Phase 2 requires both unit tests and property-based tests for comprehensive coverage:

**Unit Tests:**
- Verify specific examples and edge cases
- Test integration points between components
- Test error conditions with known inputs
- Fast execution, no external dependencies
- Use mocking for AWS services

**Property-Based Tests:**
- Verify universal properties across all inputs
- Generate random test data (CloudTrail events, ARNs, scores)
- Minimum 100 iterations per property test
- Catch edge cases that unit tests miss
- Use Hypothesis library for Python

**Complementary Nature:**
- Unit tests: "Does this specific case work?"
- Property tests: "Does this work for ALL cases?"
- Together: Comprehensive correctness validation

### Property-Based Testing Configuration

**Library:** Hypothesis for Python

**Configuration:**
```python
from hypothesis import given, settings, strategies as st

@settings(max_examples=100, deadline=None)
@given(
    event=st.builds(generate_cloudtrail_event),
    identity_arn=st.from_regex(r'arn:aws:iam::\d{12}:(user|role)/.+')
)
def test_property_event_normalization_roundtrip(event, identity_arn):
    """
    Feature: phase-2-infrastructure-backend-foundation
    Property 1: Event Normalization Round-Trip
    
    For any valid CloudTrail event, normalizing then serializing then 
    normalizing should produce equivalent Event_Summary.
    """
    # Normalize event
    event_summary_1 = normalize_event(event)
    
    # Serialize to JSON and back
    json_str = json.dumps(event_summary_1)
    event_dict = json.loads(json_str)
    
    # Normalize again (treating as CloudTrail event)
    event_summary_2 = normalize_event_summary(event_dict)
    
    # Assert equivalence
    assert event_summary_1['event_id'] == event_summary_2['event_id']
    assert event_summary_1['identity_arn'] == event_summary_2['identity_arn']
    assert event_summary_1['event_type'] == event_summary_2['event_type']
    # ... assert all required fields match
```

**Test Tagging Format:**
```python
"""
Feature: {feature_name}
Property {number}: {property_text}

{Description of what the property validates}
"""
```

**Minimum Iterations:** 100 per property test (configured via @settings decorator)


### Test Data Generators

**CloudTrail Event Generator:**
```python
from hypothesis import strategies as st

def generate_cloudtrail_event():
    """Generate random valid CloudTrail event."""
    return st.fixed_dictionaries({
        'eventID': st.uuids().map(str),
        'eventName': st.sampled_from([
            'CreateUser', 'DeleteUser', 'AttachUserPolicy',
            'AssumeRole', 'CreateAccessKey', 'RunInstances'
        ]),
        'eventTime': st.datetimes().map(lambda dt: dt.isoformat() + 'Z'),
        'userIdentity': st.fixed_dictionaries({
            'type': st.sampled_from(['IAMUser', 'AssumedRole', 'AWSService']),
            'arn': generate_identity_arn(),
            'accountId': st.from_regex(r'\d{12}')
        }),
        'sourceIPAddress': st.ip_addresses().map(str),
        'userAgent': st.text(min_size=1, max_size=100),
        'requestParameters': st.dictionaries(
            keys=st.text(min_size=1, max_size=50),
            values=st.text(min_size=1, max_size=100)
        )
    })

def generate_identity_arn():
    """Generate random valid identity ARN."""
    return st.builds(
        lambda account, name: f'arn:aws:iam::{account}:user/{name}',
        account=st.from_regex(r'\d{12}'),
        name=st.text(alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')), min_size=1, max_size=64)
    )
```

**Incident Generator:**
```python
def generate_incident():
    """Generate random incident for testing."""
    return st.fixed_dictionaries({
        'incident_id': st.uuids().map(str),
        'identity_arn': generate_identity_arn(),
        'detection_type': st.sampled_from([
            'privilege_escalation', 'unusual_access', 'suspicious_activity'
        ]),
        'severity': st.sampled_from(['Low', 'Moderate', 'High', 'Very High', 'Critical']),
        'confidence': st.floats(min_value=0, max_value=100),
        'status': st.sampled_from(['open', 'investigating', 'resolved', 'false_positive']),
        'creation_timestamp': st.datetimes().map(lambda dt: dt.isoformat() + 'Z')
    })
```

### Unit Test Examples

**Test Event Normalizer:**
```python
def test_normalize_event_extracts_identity_arn():
    """Test that Event_Normalizer extracts identity ARN correctly."""
    event = {
        'eventID': 'abc123',
        'eventName': 'CreateUser',
        'eventTime': '2024-01-15T10:30:00Z',
        'userIdentity': {
            'type': 'IAMUser',
            'arn': 'arn:aws:iam::123456789012:user/alice'
        },
        'sourceIPAddress': '203.0.113.42',
        'userAgent': 'aws-cli/2.13.0'
    }
    
    result = normalize_event(event)
    
    assert result['identity_arn'] == 'arn:aws:iam::123456789012:user/alice'

def test_normalize_event_handles_missing_required_field():
    """Test that Event_Normalizer rejects events with missing required fields."""
    event = {
        'eventID': 'abc123',
        # Missing eventName
        'eventTime': '2024-01-15T10:30:00Z',
        'userIdentity': {
            'type': 'IAMUser',
            'arn': 'arn:aws:iam::123456789012:user/alice'
        }
    }
    
    with pytest.raises(ValidationError) as exc_info:
        normalize_event(event)
    
    assert 'eventName' in str(exc_info.value)
```

**Test Incident Processor:**
```python
def test_incident_processor_generates_unique_uuids():
    """Test that Incident_Processor generates unique incident IDs."""
    finding = {
        'identity_arn': 'arn:aws:iam::123456789012:user/alice',
        'detection_type': 'privilege_escalation',
        'severity': 'High',
        'confidence': 85.5
    }
    
    # Create multiple incidents
    incident_ids = set()
    for _ in range(100):
        incident = create_incident(finding)
        incident_ids.add(incident['incident_id'])
    
    # All IDs should be unique
    assert len(incident_ids) == 100
    
    # All IDs should be valid UUIDs
    for incident_id in incident_ids:
        uuid.UUID(incident_id)  # Raises ValueError if invalid

def test_incident_processor_prevents_duplicates():
    """Test that Incident_Processor prevents duplicate incidents within 24 hours."""
    finding = {
        'identity_arn': 'arn:aws:iam::123456789012:user/alice',
        'detection_type': 'privilege_escalation',
        'severity': 'High',
        'confidence': 85.5,
        'related_event_ids': ['event1']
    }
    
    # Create first incident
    incident1 = create_incident(finding)
    
    # Try to create duplicate within 24 hours
    finding['related_event_ids'] = ['event2']
    incident2 = create_incident(finding)
    
    # Should return same incident ID with updated event IDs
    assert incident1['incident_id'] == incident2['incident_id']
    assert 'event1' in incident2['related_event_ids']
    assert 'event2' in incident2['related_event_ids']
```

### Integration Test Examples

**Test Event Processing Pipeline:**
```python
@pytest.mark.integration
def test_event_processing_pipeline_end_to_end():
    """Test complete event flow from CloudTrail to DynamoDB."""
    # Inject CloudTrail event via EventBridge
    event = generate_sample_cloudtrail_event()
    inject_event_to_eventbridge(event)
    
    # Wait for processing
    time.sleep(5)
    
    # Verify Event_Summary in DynamoDB
    event_summary = get_event_from_dynamodb(event['eventID'])
    assert event_summary is not None
    assert event_summary['identity_arn'] == event['userIdentity']['arn']
    
    # Verify Identity_Profile updated
    identity_profile = get_identity_profile(event['userIdentity']['arn'])
    assert identity_profile is not None
    assert identity_profile['activity_count'] > 0
```

### Test Coverage Goals

**Unit Test Coverage:**
- Minimum 80% code coverage
- 100% coverage of error handling paths
- All edge cases explicitly tested

**Property Test Coverage:**
- All 24 correctness properties implemented
- Minimum 100 iterations per property
- Edge case generators for boundary conditions

**Integration Test Coverage:**
- All Lambda functions tested end-to-end
- All API endpoints tested with real DynamoDB
- Event processing pipeline tested completely


## Summary

### Phase 2 Deliverables

**Infrastructure (Terraform):**
- 8 service-based modules (lambda, dynamodb, eventbridge, apigateway, cloudtrail, sns, cloudwatch, kms)
- Dev and prod environment configurations
- Remote state management with S3 and DynamoDB locking
- Deployment and verification scripts

**DynamoDB Tables:**
- 5 tables: Identity_Profile, Blast_Radius_Score, Incident, Event_Summary, Trust_Relationship
- 13 Global Secondary Indexes for optimized queries
- On-demand billing, encryption at rest, TTL configuration
- Point-in-time recovery for critical tables

**Lambda Functions:**
- 6 functions: Event_Normalizer, Detection_Engine, Incident_Processor, Identity_Collector, Score_Engine, API_Handler
- Structured JSON logging with correlation IDs
- IAM roles with least-privilege permissions
- Dead letter queues and retry logic
- Shared utilities for logging, DynamoDB, validation

**API Gateway:**
- 11 REST endpoints (10 routes, 11 operations including PATCH) for identities, scores, incidents, events, trust relationships
- IAM authorization with SigV4
- Pagination support with next_token
- CORS configuration for frontend access
- Request/response validation

**Observability:**
- CloudWatch log groups with structured logging
- CloudWatch metrics for Lambda, DynamoDB, API Gateway
- CloudWatch alarms for errors, throttling, DLQ messages
- CloudWatch dashboards for system overview and performance
- CloudWatch Insights queries for troubleshooting

**Testing Infrastructure:**
- Sample CloudTrail events for common IAM, STS, Organizations, EC2 operations
- Event injection script for dev environment
- Test data seeding script
- Unit, integration, and property-based test structure

**Documentation:**
- Architecture diagrams and data flow
- DynamoDB schema with access patterns
- API reference with request/response examples
- Terraform module documentation
- Deployment procedures
- Monitoring and troubleshooting guides

### Phase 2 Limitations

**Explicitly Not Implemented:**
- Detection rules and suspicious behavior analysis (Detection_Engine is placeholder)
- Scoring algorithms and risk calculations (Score_Engine creates arbitrary values)
- Complex trust relationship analysis (Identity_Collector records basic edges only)
- Business intelligence and advanced analytics
- Frontend dashboard

**Placeholder Components:**
- Detection_Engine: Logs events, defines interfaces, forwards to Incident_Processor
- Score_Engine: Creates records with score=50, severity=Moderate for testing
- Both include interface definitions for future implementation

### Success Criteria

Phase 2 is complete when:

1. All Terraform modules deploy successfully in dev and prod
2. CloudTrail events flow through EventBridge to Event_Normalizer
3. Event_Normalizer stores Event_Summary in DynamoDB and invokes downstream functions
4. Incident_Processor creates incidents and sends SNS alerts
5. Identity_Collector updates Identity_Profile and Trust_Relationship tables
6. API Gateway serves data from all DynamoDB tables with pagination
7. CloudWatch dashboards display system metrics
8. Sample events can be injected and processed end-to-end
9. All 24 correctness properties are implemented as property-based tests
10. Unit test coverage exceeds 80%

### Next Steps (Future Phases)

**Phase 3: Detection Logic**
- Implement detection rules in Detection_Engine
- Pattern matching for privilege escalation, unusual access, suspicious activity
- Confidence scoring for detections
- False positive reduction

**Phase 4: Scoring Logic**
- Implement blast radius calculation in Score_Engine
- Factor in permissions, trust relationships, activity patterns
- Trend analysis and score change tracking
- Risk prioritization

**Phase 5: Frontend Dashboard**
- React dashboard for incident management
- Identity risk visualization
- Score trending and analytics
- Alert configuration

**Phase 6: Advanced Features**
- Graph analysis of trust relationships
- Automated response actions
- Integration with SIEM systems
- Multi-region deployment

