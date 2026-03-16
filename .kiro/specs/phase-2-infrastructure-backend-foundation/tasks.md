# Implementation Plan: Phase 2 Infrastructure and Backend Foundation

## Overview

This implementation plan translates the Phase 2 requirements and design into actionable engineering tasks. Phase 2 establishes the complete infrastructure foundation and service skeletons for Radius, a cloud security platform that measures and reduces the blast radius of identity-based attacks in AWS Organizations.

**Implementation Language:** Python 3.11

**Key Deliverables:**
- Modular Terraform infrastructure with dev/prod environments
- Five DynamoDB tables with 13 Global Secondary Indexes
- Six Lambda functions with IAM roles and CloudWatch integration
- CloudTrail configuration with EventBridge routing
- API Gateway with 11 REST endpoints
- SNS alerting infrastructure
- CloudWatch dashboards, metrics, and alarms
- Sample CloudTrail events and testing scripts
- Comprehensive documentation

**Important Notes:**
- Detection_Engine and Score_Engine are PLACEHOLDER functions (logging only)
- Identity_Collector records basic trust edges only (no complex analysis)
- Event_Normalizer invokes Identity_Collector asynchronously (NOT triggered by EventBridge directly)
- Each task produces one clear deliverable
- Tasks are organized into 6 milestones for cleaner execution

**Priority Labels:**
- **must-have**: Critical for Phase 2 functionality
- **should-have**: Important but not blocking
- **nice-to-have**: Optional enhancements

**Task Notation:**
- Tasks without `*` are required
- Tasks with `*` are optional (nice-to-have)

## Tasks

### Milestone 1: Repository Bootstrap and Foundation

- [x] 0. Bootstrap repository structure (must-have)
  - Create .gitignore with Terraform, Python, and AWS-specific exclusions
  - Create folder structure: backend/, backend/common/, backend/functions/, backend/tests/
  - Create folder structure: infra/, infra/modules/, infra/envs/dev/, infra/envs/prod/
  - Create folder structure: docs/, docs/architecture/, sample-data/, scripts/
  - Create README.md with project overview, architecture summary, and setup instructions
  - **Deliverable:** Complete repository structure with .gitignore, folders, and README.md
  - _Requirements: 1.1, 1.2_

- [x] 1. Initialize Terraform project structure and remote state backend (must-have)
  - Create root module files: infra/main.tf, infra/variables.tf, infra/outputs.tf, infra/backend.tf, infra/versions.tf
  - Configure S3 backend for Terraform state with DynamoDB locking
  - Create backend configuration files: infra/envs/dev/backend.tfvars, infra/envs/prod/backend.tfvars
  - **Deliverable:** Terraform root module with S3 backend configuration
  - _Requirements: 1.1, 1.2, 1.5_

- [x] 2. Create documentation stubs for later completion (should-have)
  - Create docs/architecture.md with placeholder sections
  - Create docs/database-schema.md with placeholder sections
  - Create docs/api-reference.md with placeholder sections
  - Create docs/terraform-modules.md with placeholder sections
  - Create docs/deployment.md with placeholder sections
  - Create docs/monitoring.md with placeholder sections
  - Create docs/phase-2-scope.md with placeholder sections
  - **Deliverable:** Documentation stub files ready for content
  - _Requirements: 13.1-13.8_

### Milestone 2: Infrastructure Core (Terraform Modules)

- [x] 3. Create KMS module for encryption keys (must-have)
  - Create infra/modules/kms/ with main.tf, variables.tf, outputs.tf
  - Define KMS key resources for DynamoDB, Lambda, SNS, CloudTrail
  - Configure key rotation and key policies
  - **Deliverable:** KMS module with encryption keys for all services
  - _Requirements: 1.2, 2.27_

- [x] 4. Create DynamoDB module skeleton (must-have)
  - Create infra/modules/dynamodb/ with main.tf, variables.tf, outputs.tf, gsi.tf
  - Define module inputs for table configuration and environment settings
  - Define module outputs for table names, ARNs, and GSI names
  - **Deliverable:** DynamoDB module structure ready for table definitions
  - _Requirements: 1.2, 1.3, 1.4, 2.23_

- [x] 5. Implement Identity_Profile table (must-have)
  - Define table resource with identity_arn as partition key
  - Add IdentityTypeIndex GSI (identity_type, account_id) with ALL projection
  - Add AccountIndex GSI (account_id, last_activity_timestamp) with ALL projection
  - Configure on-demand billing, KMS encryption, and point-in-time recovery
  - **Deliverable:** Identity_Profile table with 2 GSIs
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.23, 2.24, 2.27_

- [x] 6. Implement Blast_Radius_Score table (must-have)
  - Define table resource with identity_arn as partition key
  - Add ScoreRangeIndex GSI (severity_level, score_value) with ALL projection
  - Add SeverityIndex GSI (severity_level, calculation_timestamp) with KEYS_ONLY projection
  - Configure on-demand billing, KMS encryption, and point-in-time recovery
  - **Deliverable:** Blast_Radius_Score table with 2 GSIs
  - _Requirements: 2.5, 2.6, 2.7, 2.8, 2.23, 2.24, 2.27_

- [x] 7. Implement Incident table (must-have)
  - Define table resource with incident_id as partition key
  - Add StatusIndex GSI (status, creation_timestamp) with ALL projection
  - Add SeverityIndex GSI (severity, creation_timestamp) with ALL projection
  - Add IdentityIndex GSI (identity_arn, creation_timestamp) with KEYS_ONLY projection
  - Configure on-demand billing, KMS encryption, point-in-time recovery, and TTL
  - **Deliverable:** Incident table with 3 GSIs and TTL configuration
  - _Requirements: 2.9, 2.10, 2.11, 2.12, 2.13, 2.23, 2.24, 2.26, 2.27_

- [x] 8. Implement Event_Summary table (must-have)
  - Define table resource with composite key (identity_arn, timestamp)
  - Add EventIdIndex GSI (event_id) with ALL projection for direct event lookup
  - Add EventTypeIndex GSI (event_type, timestamp) with KEYS_ONLY projection
  - Add TimeRangeIndex GSI (date_partition, timestamp) with ALL projection
  - Configure on-demand billing, KMS encryption, and TTL for 90-day expiration
  - **Deliverable:** Event_Summary table with 3 GSIs and TTL configuration
  - _Requirements: 2.14, 2.15, 2.16, 2.17, 2.18, 2.23, 2.25, 2.27_

- [x] 9. Implement Trust_Relationship table (must-have)
  - Define table resource with composite key (source_arn, target_arn)
  - Add RelationshipTypeIndex GSI (relationship_type, discovery_timestamp) with ALL projection
  - Add TargetAccountIndex GSI (target_account_id, discovery_timestamp) with KEYS_ONLY projection
  - Configure on-demand billing and KMS encryption
  - **Deliverable:** Trust_Relationship table with 2 GSIs
  - _Requirements: 2.19, 2.20, 2.21, 2.22, 2.23, 2.27_

- [ ] 10. Create Lambda module for function provisioning (must-have)
  - Create infra/modules/lambda/ with main.tf, variables.tf, outputs.tf, iam.tf
  - Define module inputs for function configurations (memory, timeout, concurrency)
  - Define IAM role and policy resources with least-privilege permissions
  - Define module outputs for function ARNs, names, and role ARNs
  - **Deliverable:** Lambda module structure ready for function definitions
  - _Requirements: 1.2, 1.3, 1.4, 3.1, 3.5_

- [ ] 11. Create EventBridge module for event routing (must-have)
  - Create infra/modules/eventbridge/ with main.tf, variables.tf, outputs.tf
  - Define module inputs for event patterns and Lambda target ARNs
  - Define module outputs for rule ARNs and event bus ARN
  - **Deliverable:** EventBridge module ready for rule definitions
  - _Requirements: 1.2, 1.3, 1.4, 4.10_

- [ ] 12. Create API Gateway module for REST endpoints (must-have)
  - Create infra/modules/apigateway/ with main.tf, variables.tf, outputs.tf, endpoints.tf
  - Define module inputs for Lambda function ARN and CORS configuration
  - Define module outputs for API endpoint URL, API ID, and API ARN
  - **Deliverable:** API Gateway module ready for endpoint definitions
  - _Requirements: 1.2, 1.3, 1.4, 5.1_

- [ ] 13. Create CloudTrail module for audit logging (must-have)
  - Create infra/modules/cloudtrail/ with main.tf, variables.tf, outputs.tf, s3.tf
  - Define module inputs for organization-wide vs single-account configuration
  - Define S3 bucket resources with lifecycle policies and encryption
  - Define module outputs for trail ARN and S3 bucket name
  - **Deliverable:** CloudTrail module with S3 bucket and trail configuration
  - _Requirements: 1.2, 1.3, 1.4, 4.1, 4.5_

- [ ] 14. Create SNS module for alerting (must-have)
  - Create infra/modules/sns/ with main.tf, variables.tf, outputs.tf
  - Define module inputs for subscription endpoints
  - Define module outputs for topic ARNs
  - **Deliverable:** SNS module ready for topic and subscription definitions
  - _Requirements: 1.2, 1.3, 1.4, 10.1_

- [ ] 15. Create CloudWatch module for observability (must-have)
  - Create infra/modules/cloudwatch/ with main.tf, variables.tf, outputs.tf, alarms.tf, dashboards.tf
  - Define module inputs for resource ARNs and alarm thresholds
  - Define module outputs for log group names
  - **Deliverable:** CloudWatch module ready for log groups, alarms, and dashboards
  - _Requirements: 1.2, 1.3, 1.4, 11.1_

- [ ] 16. Configure environment-specific Terraform (must-have)
  - [ ] 16.1 Configure dev environment
    - Create infra/envs/dev/main.tf with module instantiations
    - Create infra/envs/dev/terraform.tfvars with dev-specific values (single-account CloudTrail, minimal resources, 7-day logs)
    - **Deliverable:** Dev environment Terraform configuration
    - _Requirements: 1.7, 1.8, 1.9_
  
  - [ ] 16.2 Configure prod environment
    - Create infra/envs/prod/main.tf with module instantiations
    - Create infra/envs/prod/terraform.tfvars with prod-specific values (org-wide CloudTrail, high availability, 30-day logs)
    - **Deliverable:** Prod environment Terraform configuration
    - _Requirements: 1.7, 1.8, 1.10_

- [ ] 17. Verify Terraform module dependencies and composition (must-have)
  - Review module composition in root main.tf to ensure correct dependency flow
  - Verify KMS → DynamoDB/SNS → Lambda → EventBridge/API Gateway → CloudTrail → CloudWatch
  - Run terraform init and terraform validate in dev environment
  - **Deliverable:** Validated Terraform configuration with correct dependency graph
  - _Requirements: 1.6_

### Milestone 3: Processing Pipeline (Lambda Functions)

- [ ] 18. Create shared Python utilities for Lambda functions (must-have)
  - [ ] 18.1 Create backend/common/ directory structure
    - Create backend/common/__init__.py
    - Create backend/common/logging_utils.py for structured JSON logging
    - Create backend/common/dynamodb_utils.py for DynamoDB operations
    - Create backend/common/validation.py for input validation
    - Create backend/common/errors.py for custom exception classes
    - **Deliverable:** Shared utilities directory structure
    - _Requirements: 3.13, 3.17_
  
  - [ ] 18.2 Implement logging_utils.py
    - Implement get_logger() function with structured JSON formatting
    - Implement log_error() function with correlation ID, error type, and stack trace
    - Implement log_request() function for request tracing
    - Include correlation ID generation and propagation
    - **Deliverable:** Logging utilities with correlation ID support
    - _Requirements: 3.13, 3.17, 11.13, 11.14_
  
  - [ ] 18.3 Implement dynamodb_utils.py
    - Implement get_dynamodb_client() function with boto3 initialization
    - Implement put_item() wrapper with error handling and retry logic
    - Implement query_gsi() wrapper for GSI queries with pagination support
    - Implement get_item() wrapper for primary key lookups
    - Implement update_item() wrapper for atomic updates
    - **Deliverable:** DynamoDB utilities with retry logic
    - _Requirements: 3.18_
  
  - [ ] 18.4 Implement validation.py
    - Implement validate_arn() function for ARN format validation
    - Implement validate_timestamp() function for ISO 8601 validation
    - Implement validate_required_fields() function for CloudTrail events
    - Implement sanitize_event_data() function to exclude sensitive data
    - **Deliverable:** Validation utilities for CloudTrail events
    - _Requirements: 6.3, 6.4, 6.7_
  
  - [ ] 18.5 Implement errors.py
    - Define RadiusError base exception class
    - Define ValidationError for input validation failures
    - Define DynamoDBError for database operation failures
    - Define EventProcessingError for event handling failures
    - **Deliverable:** Custom exception classes for error handling
    - _Requirements: 3.17_

- [ ] 19. Implement Event_Normalizer Lambda function (must-have)
  - [ ] 19.1 Create Event_Normalizer function structure
    - Create backend/functions/event_normalizer/ directory
    - Create handler.py with lambda_handler entry point
    - Create normalizer.py with event parsing logic
    - Create requirements.txt with boto3, python-dateutil dependencies
    - **Deliverable:** Event_Normalizer function skeleton
    - _Requirements: 3.1, 6.1_
  
  - [ ] 19.2 Implement CloudTrail event parsing and validation
    - Extract identity ARN, event type, timestamp, source IP, user agent from CloudTrail events
    - Normalize timestamp to ISO 8601 and identity ARN to consistent format
    - Validate required fields (eventName, userIdentity, eventTime) are present
    - Log validation errors with event ID and skip invalid events
    - **Deliverable:** Event parsing and validation logic
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_
  
  - [ ] 19.3 Implement Event_Summary storage
    - Store normalized event in Event_Summary DynamoDB table
    - Generate date_partition field (YYYY-MM-DD format) for TimeRangeIndex
    - Exclude sensitive data and large payloads (>10KB)
    - Handle DynamoDB write errors with retry logic
    - **Deliverable:** Event storage with sanitization
    - _Requirements: 6.7, 6.8_
  
  - [ ] 19.4 Implement downstream invocations
    - Invoke Detection_Engine Lambda asynchronously with Event_Summary
    - Invoke Identity_Collector Lambda asynchronously with event data
    - Handle invocation errors and log failures
    - **Deliverable:** Async invocations to Detection_Engine and Identity_Collector
    - _Requirements: 6.9_

- [ ] 20. Implement Detection_Engine Lambda function (PLACEHOLDER) (must-have)
  - [ ] 20.1 Create Detection_Engine function structure
    - Create backend/functions/detection_engine/ directory
    - Create handler.py with lambda_handler entry point
    - Create interfaces.py with detection rule interface definitions
    - Create requirements.txt with boto3 dependency
    - **Deliverable:** Detection_Engine function skeleton
    - _Requirements: 3.1, 7.1_
  
  - [ ] 20.2 Implement placeholder detection logic
    - Log received Event_Summary with event ID, identity ARN, and event type
    - Define DetectionRule interface class with rule_id, rule_name, and evaluate() method signature
    - Define Finding data structure with identity_arn, detection_type, severity, confidence, related_event_ids
    - Include placeholder methods with logging statements for future detection rules
    - Forward Event_Summary data to Incident_Processor for pipeline testing
    - **Deliverable:** Placeholder detection logic with interface definitions
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

- [ ] 21. Implement Identity_Collector Lambda function (must-have)
  - [ ] 21.1 Create Identity_Collector function structure
    - Create backend/functions/identity_collector/ directory
    - Create handler.py with lambda_handler entry point
    - Create collector.py with identity profile logic
    - Create requirements.txt with boto3 dependency
    - **Deliverable:** Identity_Collector function skeleton
    - _Requirements: 3.1, 8.10_
  
  - [ ] 21.2 Implement Identity_Profile creation and updates
    - Extract identity type (IAMUser, AssumedRole, AWSService) from ARN
    - Extract account ID from ARN using standard ARN parsing
    - Create or update Identity_Profile in DynamoDB
    - Update last_activity_timestamp field on every event
    - Store identity tags when available in CloudTrail metadata
    - **Deliverable:** Identity profile management logic
    - _Requirements: 8.10, 8.11, 8.12, 8.13, 8.14_
  
  - [ ] 21.3 Implement Trust_Relationship recording
    - Detect AssumeRole events from CloudTrail
    - Extract source identity ARN (who assumed) and target role ARN (what was assumed)
    - Create Trust_Relationship record with source_arn and target_arn
    - Record only basic trust edges without analysis or permission evaluation
    - **Deliverable:** Basic trust relationship recording
    - _Requirements: 8.15, 8.16, 8.17_
  
  - [ ] 21.4 Implement identity deletion handling
    - Detect identity deletion events (DeleteUser, DeleteRole)
    - Mark Identity_Profile as inactive rather than deleting record
    - Preserve historical data for audit purposes
    - **Deliverable:** Identity deletion handling
    - _Requirements: 8.18_

- [ ] 22. Implement Incident_Processor Lambda function (must-have)
  - [ ] 22.1 Create Incident_Processor function structure
    - Create backend/functions/incident_processor/ directory
    - Create handler.py with lambda_handler entry point
    - Create processor.py with incident creation logic
    - Create requirements.txt with boto3 dependency
    - **Deliverable:** Incident_Processor function skeleton
    - _Requirements: 3.1, 8.1_
  
  - [ ] 22.2 Implement incident creation
    - Validate required fields (identity_arn, detection_type, severity) are present
    - Generate unique incident ID using UUID v4 format
    - Store Incident record in DynamoDB with status "open"
    - Record creation_timestamp and update_timestamp
    - **Deliverable:** Incident creation logic
    - _Requirements: 8.1, 8.2, 8.3, 8.9_
  
  - [ ] 22.3 Implement incident deduplication
    - Query IdentityIndex GSI for incidents with same identity_arn
    - Filter by detection_type and creation_timestamp within last 24 hours
    - If duplicate found, update existing incident with new event_ids instead of creating new incident
    - **Deliverable:** Incident deduplication logic
    - _Requirements: 8.7_
  
  - [ ] 22.4 Implement SNS alerting for high-severity incidents
    - Publish notification to Alert_Topic for High, Very High, or Critical severity
    - Include incident_id, identity_arn, detection_type, severity, confidence in message
    - Include dashboard link in notification
    - Publish immediately without batching for Critical and Very High severity
    - **Deliverable:** SNS alerting for high-severity incidents
    - _Requirements: 8.4, 8.5, 8.6_
  
  - [ ] 22.5 Implement incident status transitions
    - Support status transitions: open → investigating → resolved, open → false_positive
    - Record update_timestamp on status changes
    - Preserve status_history with timestamps
    - **Deliverable:** Incident status management
    - _Requirements: 8.8, 8.9_

- [ ] 23. Implement Score_Engine Lambda function (PLACEHOLDER) (must-have)
  - [ ] 23.1 Create Score_Engine function structure
    - Create backend/functions/score_engine/ directory
    - Create handler.py with lambda_handler entry point
    - Create interfaces.py with scoring rule interface definitions
    - Create requirements.txt with boto3 dependency
    - **Deliverable:** Score_Engine function skeleton
    - _Requirements: 3.1, 7.7_
  
  - [ ] 23.2 Implement placeholder scoring logic
    - Log invocations with identity_arn and timestamp
    - Define ScoringRule interface class with rule_id, rule_name, and calculate() method signature
    - Define score data structure with identity_arn, score_value, severity_level, calculation_timestamp, contributing_factors
    - Implement classify_severity() function (0-19: Low, 20-39: Moderate, 40-59: High, 60-79: Very High, 80-100: Critical)
    - Include placeholder methods with logging statements for future scoring algorithms
    - **Deliverable:** Placeholder scoring logic with interface definitions
    - _Requirements: 7.7, 7.8, 7.9, 7.12, 7.13_
  
  - [ ] 23.3 Create placeholder Blast_Radius_Score records
    - Create records with arbitrary default values (score: 50, severity: Moderate)
    - Store in Blast_Radius_Score DynamoDB table
    - Records exist ONLY for testing data pipeline and API endpoints
    - **Deliverable:** Placeholder score records for testing
    - _Requirements: 7.10, 7.11_

- [ ] 24. Configure Lambda functions in Terraform (must-have)
  - [ ] 24.1 Implement Lambda function resources
    - Define aws_lambda_function resources for all 6 functions
    - Configure memory, timeout, and concurrency per function (Event_Normalizer: 512MB/30s, Detection_Engine: 1024MB/60s, Incident_Processor: 512MB/30s, Identity_Collector: 512MB/30s, Score_Engine: 1024MB/60s, API_Handler: 256MB/10s)
    - Configure runtime as python3.11 and architecture as arm64
    - Configure environment variables for DynamoDB table names, SNS topic ARNs, region
    - Configure dead-letter queues for event-driven functions
    - **Deliverable:** Lambda function Terraform resources
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.12, 3.16_
  
  - [ ] 24.2 Implement IAM roles and policies
    - Create IAM role for Event_Normalizer with EventBridge, DynamoDB, Lambda invoke permissions
    - Create IAM role for Detection_Engine with DynamoDB read, Lambda invoke permissions
    - Create IAM role for Incident_Processor with DynamoDB write, SNS publish permissions
    - Create IAM role for Identity_Collector with DynamoDB write permissions
    - Create IAM role for Score_Engine with DynamoDB read/write permissions
    - Create IAM role for API_Handler with DynamoDB read, Incident table write permissions
    - **Deliverable:** IAM roles and policies for all Lambda functions
    - _Requirements: 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11_
  
  - [ ] 24.3 Configure CloudWatch Logs integration
    - Create CloudWatch log groups for all Lambda functions
    - Configure log retention periods (dev: 7 days, prod: 30 days)
    - Grant Lambda functions permission to write to CloudWatch Logs
    - **Deliverable:** CloudWatch Logs configuration for Lambda functions
    - _Requirements: 3.13, 3.14_

- [ ] 25. Configure EventBridge routing rules (must-have)
  - Define event pattern to filter IAM, STS, Organizations, EC2 management events
  - Set Event_Normalizer Lambda as target
  - Grant EventBridge permission to invoke Event_Normalizer
  - Configure at-least-once delivery semantics with retry policy
  - Configure dead-letter queue for failed events
  - **Deliverable:** EventBridge rule routing CloudTrail events to Event_Normalizer
  - _Requirements: 4.10, 4.11, 4.12, 4.13, 4.14_

- [ ] 26. Configure CloudTrail and S3 storage (must-have)
  - [ ] 26.1 Create S3 bucket for CloudTrail logs
    - Create S3 bucket with encryption enabled
    - Configure bucket policy to allow CloudTrail write access
    - Block all public access
    - Enable versioning for log integrity
    - **Deliverable:** S3 bucket for CloudTrail logs
    - _Requirements: 4.5, 4.7, 4.9_
  
  - [ ] 26.2 Configure S3 lifecycle policies
    - Transition logs to Glacier after 90 days
    - Delete logs after 365 days
    - **Deliverable:** S3 lifecycle policies for cost optimization
    - _Requirements: 4.8_
  
  - [ ] 26.3 Create CloudTrail trail
    - Create organization-wide trail for prod environment
    - Create single-account trail for dev environment
    - Enable EventBridge integration for real-time processing
    - Enable log file validation for integrity verification
    - Configure KMS encryption for logs
    - **Deliverable:** CloudTrail trail with EventBridge integration
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6, 4.7_

- [ ] 27. Configure SNS alerting infrastructure (must-have)
  - [ ] 27.1 Create SNS topic for incident alerts
    - Create Alert_Topic with KMS encryption
    - Configure message attributes for severity filtering
    - **Deliverable:** SNS topic for incident alerts
    - _Requirements: 10.1, 10.4, 10.5_
  
  - [ ] 27.2 Configure SNS subscriptions
    - Add email subscription endpoints for security team
    - Add HTTPS webhook subscription endpoints for external systems
    - Configure subscription filter policies by severity level
    - **Deliverable:** SNS subscriptions for alerting
    - _Requirements: 10.2, 10.3_
  
  - [ ] 27.3 Format incident notification messages
    - Include incident_id, identity_arn, detection_type, severity, confidence, creation_timestamp
    - Include dashboard link to incident detail page
    - Format severity levels with visual indicators in subject line
    - **Deliverable:** Incident notification message format
    - _Requirements: 10.6, 10.7, 10.8_

### Milestone 4: API Layer

- [ ] 28. Implement API_Handler Lambda function (must-have)
  - [ ] 28.1 Create API_Handler function structure
    - Create backend/functions/api_handler/ directory
    - Create handler.py with lambda_handler entry point
    - Create handlers/ subdirectory for endpoint-specific handlers
    - Create requirements.txt with boto3 dependency
    - **Deliverable:** API_Handler function skeleton
    - _Requirements: 3.1, 9.1_
  
  - [ ] 28.2 Implement pagination utilities
    - Encode DynamoDB LastEvaluatedKey as base64 next_token
    - Decode next_token to ExclusiveStartKey for subsequent queries
    - Limit result sets to maximum 100 items per request (default 25)
    - Include next_token in response metadata when more results available
    - **Deliverable:** Pagination utilities for API responses
    - _Requirements: 9.12, 9.13_
  
  - [ ] 28.3 Implement response formatting
    - Return consistent JSON structure: {data: [...], metadata: {count, next_token, query_time}}
    - Use appropriate HTTP status codes (200, 400, 404, 500)
    - **Deliverable:** Response formatting utilities
    - _Requirements: 5.16, 5.17, 9.14_
  
  - [ ] 28.4 Implement request validation and error handling
    - Validate query parameters (data types, ranges)
    - Return 400 for invalid parameters with validation details
    - Return 404 for resources not found
    - Return 500 for DynamoDB errors with error message
    - Log all requests with correlation ID, endpoint, parameters, and response time
    - **Deliverable:** Request validation and error handling
    - _Requirements: 9.11, 9.15, 9.16, 9.17, 9.18_

- [ ] 29. Implement identity endpoints (must-have)
  - [ ] 29.1 Implement GET /identities endpoint
    - Query Identity_Profile table using IdentityTypeIndex or AccountIndex based on parameters
    - Support query parameters: identity_type, account_id, limit, next_token
    - Implement pagination using DynamoDB LastEvaluatedKey
    - Return JSON response with data array and metadata
    - **Deliverable:** GET /identities endpoint
    - _Requirements: 5.5, 9.1_
  
  - [ ] 29.2 Implement GET /identities/{arn} endpoint
    - Retrieve specific Identity_Profile by partition key (identity_arn)
    - URL-decode ARN from path parameter
    - Return 404 if identity not found
    - **Deliverable:** GET /identities/{arn} endpoint
    - _Requirements: 5.6, 9.2_

- [ ] 30. Implement score endpoints (must-have)
  - [ ] 30.1 Implement GET /scores endpoint
    - Query Blast_Radius_Score table using ScoreRangeIndex or SeverityIndex based on filters
    - Support query parameters: severity_level, min_score, max_score, limit, next_token
    - Implement pagination using DynamoDB LastEvaluatedKey
    - Return JSON response with data array and metadata
    - **Deliverable:** GET /scores endpoint
    - _Requirements: 5.7, 9.3_
  
  - [ ] 30.2 Implement GET /scores/{arn} endpoint
    - Retrieve specific Blast_Radius_Score by partition key (identity_arn)
    - URL-decode ARN from path parameter
    - Return 404 if score not found
    - **Deliverable:** GET /scores/{arn} endpoint
    - _Requirements: 5.8, 9.4_

- [ ] 31. Implement incident endpoints (must-have)
  - [ ] 31.1 Implement GET /incidents endpoint
    - Query Incident table using StatusIndex or SeverityIndex based on filters
    - Support query parameters: status, severity, identity_arn, start_date, end_date, limit, next_token
    - Note: Unsupported query combinations (e.g., identity_arn + status without GSI support) return 400
    - Implement pagination using DynamoDB LastEvaluatedKey
    - Return JSON response with data array and metadata
    - **Deliverable:** GET /incidents endpoint
    - _Requirements: 5.9, 9.5_
  
  - [ ] 31.2 Implement GET /incidents/{id} endpoint
    - Retrieve specific Incident by partition key (incident_id)
    - Return 404 if incident not found
    - **Deliverable:** GET /incidents/{id} endpoint
    - _Requirements: 5.10, 9.6_
  
  - [ ] 31.3 Implement PATCH /incidents/{id} endpoint
    - Update incident status from request body
    - Validate status transitions (open → investigating → resolved, open → false_positive)
    - Record update_timestamp and preserve status_history
    - Return updated incident record
    - **Deliverable:** PATCH /incidents/{id} endpoint
    - _Requirements: 5.11, 9.7_

- [ ] 32. Implement event endpoints (must-have)
  - [ ] 32.1 Implement GET /events endpoint
    - Query Event_Summary table using EventTypeIndex or TimeRangeIndex based on filters
    - Support query parameters: identity_arn, event_type, start_date, end_date, limit, next_token
    - Note: Unsupported query combinations (e.g., identity_arn + event_type without composite GSI) return 400
    - Implement pagination using DynamoDB LastEvaluatedKey
    - Return JSON response with data array and metadata
    - **Deliverable:** GET /events endpoint
    - _Requirements: 5.12, 9.8_
  
  - [ ] 32.2 Implement GET /events/{id} endpoint
    - Query Event_Summary table using EventIdIndex GSI with event_id as partition key
    - Return 404 if event not found
    - **Deliverable:** GET /events/{id} endpoint
    - _Requirements: 5.13, 9.9_

- [ ] 33. Implement trust relationship endpoints (must-have)
  - Query Trust_Relationship table using appropriate GSI based on parameters
  - Support query parameters: source_arn, target_account_id, relationship_type, limit, next_token
  - Note: Unsupported query combinations return 400
  - Implement pagination using DynamoDB LastEvaluatedKey
  - Return JSON response with data array and metadata
  - **Deliverable:** GET /trust-relationships endpoint
  - _Requirements: 5.14, 9.10_

- [ ] 34. Configure API Gateway REST API (must-have)
  - [ ] 34.1 Create API Gateway REST API resource
    - Define REST API with IAM authorization
    - Enable CloudWatch logging for all requests
    - Configure CORS with appropriate allowed origins
    - **Deliverable:** API Gateway REST API resource
    - _Requirements: 5.1, 5.2, 5.3_
  
  - [ ] 34.2 Define API Gateway endpoints
    - Create resource /identities with GET method
    - Create resource /identities/{arn} with GET method
    - Create resource /scores with GET method
    - Create resource /scores/{arn} with GET method
    - Create resource /incidents with GET method
    - Create resource /incidents/{id} with GET and PATCH methods
    - Create resource /events with GET method
    - Create resource /events/{id} with GET method
    - Create resource /trust-relationships with GET method
    - **Deliverable:** API Gateway endpoint definitions (10 operations total)
    - _Requirements: 5.5-5.14_
  
  - [ ] 34.3 Configure Lambda integrations
    - Configure Lambda proxy integration for all endpoints
    - Grant API Gateway permission to invoke API_Handler Lambda
    - Configure request/response transformations for ARN encoding
    - **Deliverable:** Lambda integrations for all endpoints
    - _Requirements: 5.4, 5.15_
  
  - [ ] 34.4 Deploy API Gateway stage
    - Create deployment stage (dev or prod)
    - Enable stage-level logging and metrics
    - Output API Gateway invoke URL
    - **Deliverable:** Deployed API Gateway stage with invoke URL
    - _Requirements: 5.3_

### Milestone 5: Observability and Monitoring

- [ ] 35. Configure CloudWatch monitoring and alerting (must-have)
  - [ ] 35.1 Create CloudWatch metrics
    - Define custom metrics for Lambda invocations, errors, duration, throttles
    - Define custom metrics for DynamoDB consumed capacity and throttled requests
    - Define custom metrics for API Gateway request count, latency, 4xx/5xx errors
    - **Deliverable:** CloudWatch metrics for all services
    - _Requirements: 11.3, 11.4, 11.5_
  
  - [ ] 35.2 Create CloudWatch alarms
    - Create alarm for Lambda error rates exceeding 5% over 5 minutes
    - Create alarm for Lambda duration approaching timeout thresholds
    - Create alarm for DynamoDB throttled requests exceeding 10 per minute
    - Create alarm for dead-letter queue message counts exceeding 0
    - Create alarm for API Gateway 5xx error rates exceeding 1% over 5 minutes
    - Configure alarm actions to publish to SNS topics
    - **Deliverable:** CloudWatch alarms for operational issues
    - _Requirements: 11.6, 11.7, 11.8, 11.9, 11.10, 11.12_
  
  - [ ] 35.3 Create CloudWatch dashboards
    - Create dashboard showing Lambda invocations, errors, duration
    - Create dashboard showing DynamoDB operations, consumed capacity, throttles
    - Create dashboard showing API Gateway requests, latency, error rates
    - Create dashboard showing EventBridge rule invocations
    - **Deliverable:** CloudWatch dashboards for system observability
    - _Requirements: 11.11_

- [ ] 36. Create deployment automation scripts (must-have)
  - [ ] 36.1 Create Lambda build script
    - Create scripts/build-lambdas.sh to package Lambda functions
    - Install Python dependencies for each function
    - Create deployment zip files with function code and dependencies
    - Upload zip files to S3 for Terraform deployment
    - **Deliverable:** Lambda build and packaging script
    - _Requirements: 1.11_
  
  - [ ] 36.2 Create Terraform deployment script
    - Create scripts/deploy-infra.sh with environment selection
    - Initialize Terraform with backend configuration
    - Run terraform plan and display resource summary
    - Run terraform apply with approval
    - Validate deployment and output resource ARNs
    - **Deliverable:** Terraform deployment automation script
    - _Requirements: 1.11, 1.12_
  
  - [ ] 36.3 Create verification script
    - Create scripts/verify-deployment.sh to test deployed resources
    - Verify Lambda functions are invocable
    - Verify DynamoDB tables exist with correct GSIs
    - Verify API Gateway endpoints are accessible
    - Verify CloudTrail is delivering events to EventBridge
    - **Deliverable:** Deployment verification script
    - _Requirements: 1.12_

- [ ] 37. Verify infrastructure deployment to dev environment (must-have)
  - Run scripts/build-lambdas.sh to package all Lambda functions
  - Run scripts/deploy-infra.sh --env dev to deploy infrastructure
  - Run scripts/verify-deployment.sh --env dev to validate deployment
  - Verify all Terraform modules deployed successfully
  - Verify all Lambda functions are invocable
  - Verify all DynamoDB tables exist with correct GSIs
  - Verify API Gateway endpoints return 200 or 404 (not 500)
  - **Deliverable:** Verified infrastructure deployment (not full system verification)
  - _Requirements: 1.11, 1.12_

### Milestone 6: Testing, Documentation, and Validation

- [ ] 38. Create sample CloudTrail events for testing (must-have)
  - [ ] 38.1 Create sample IAM events
    - Create sample-data/iam-create-user.json
    - Create sample-data/iam-attach-policy.json
    - Create sample-data/iam-delete-user.json
    - **Deliverable:** Sample IAM CloudTrail events
    - _Requirements: 12.1_
  
  - [ ] 38.2 Create sample STS events
    - Create sample-data/sts-assume-role.json
    - Create sample-data/sts-get-session-token.json
    - Create sample-data/sts-get-federation-token.json
    - **Deliverable:** Sample STS CloudTrail events
    - _Requirements: 12.1, 12.2_
  
  - [ ] 38.3 Create sample Organizations events
    - Create sample-data/orgs-create-account.json
    - Create sample-data/orgs-invite-account.json
    - **Deliverable:** Sample Organizations CloudTrail events
    - _Requirements: 12.1, 12.3_
  
  - [ ] 38.4 Create sample EC2 events
    - Create sample-data/ec2-run-instances.json with IAM instance profile
    - **Deliverable:** Sample EC2 CloudTrail events
    - _Requirements: 12.1, 12.4_
  
  - [ ] 38.5 Create suspicious activity samples
    - Create sample-data/suspicious-privilege-escalation.json
    - Create sample-data/suspicious-cross-account-access.json
    - **Deliverable:** Sample suspicious activity events
    - _Requirements: 12.1, 12.5_
  
  - [ ] 38.6 Create normal activity samples
    - Create sample-data/normal-admin-operations.json
    - **Deliverable:** Sample normal activity events
    - _Requirements: 12.1, 12.6_

- [ ] 39. Create event injection and testing scripts (must-have)
  - [ ] 39.1 Create event injection script
    - Create scripts/inject-events.py to inject sample events into EventBridge
    - Support injecting individual event files or entire directories
    - Validate event JSON structure before injection
    - Support dev environment only in Phase 2
    - Log injection results (event count, success count, failure count)
    - **Deliverable:** Event injection script for testing
    - _Requirements: 12.7, 12.8, 12.9, 12.10, 12.11_
  
  - [ ] 39.2 Create test data seeding script
    - Create scripts/seed-dev-data.py to populate DynamoDB tables with test data
    - Create sample Identity_Profile records
    - Create sample Blast_Radius_Score records
    - Create sample Incident records
    - Create sample Trust_Relationship records
    - Support dev environment only
    - **Deliverable:** Test data seeding script
    - _Requirements: 12.1_

- [ ] 40. Complete architecture documentation (must-have)
  - Update docs/architecture.md with event processing pipeline description
  - Include data flow diagrams showing CloudTrail → EventBridge → Lambda → DynamoDB
  - Include Lambda function interaction diagrams
  - Include EventBridge routing diagrams
  - Clarify that Event_Normalizer invokes Identity_Collector asynchronously
  - **Deliverable:** Complete architecture documentation
  - _Requirements: 13.1, 13.8_

- [ ] 41. Complete database schema documentation (must-have)
  - Update docs/database-schema.md with all table definitions
  - Document primary keys, GSIs, and field definitions for each table
  - Include access patterns and query examples
  - Include TTL and PITR configurations
  - **Deliverable:** Complete database schema documentation
  - _Requirements: 13.2_

- [ ] 42. Complete API reference documentation (must-have)
  - Update docs/api-reference.md with all endpoint definitions
  - Document HTTP methods, request parameters, response formats
  - Include example requests and responses for each endpoint
  - Document error codes and error response formats
  - Note unsupported query combinations that return 400
  - **Deliverable:** Complete API reference documentation
  - _Requirements: 13.3_

- [ ] 43. Complete Terraform module documentation (must-have)
  - Update docs/terraform-modules.md describing module structure
  - Document module inputs, outputs, and composition patterns
  - Include logical dependency relationships (Terraform resolves automatically)
  - Document environment-specific configurations
  - **Deliverable:** Complete Terraform module documentation
  - _Requirements: 13.4_

- [ ] 44. Complete deployment documentation (must-have)
  - Update docs/deployment.md with deployment procedures
  - Document prerequisites (AWS credentials, Terraform, Python)
  - Document deployment steps for dev and prod environments
  - Document verification procedures and troubleshooting
  - Include rollback procedures
  - **Deliverable:** Complete deployment documentation
  - _Requirements: 13.5_

- [ ] 45. Complete monitoring documentation (must-have)
  - Update docs/monitoring.md describing monitoring setup
  - Document CloudWatch dashboards and their metrics
  - Document alarm configurations and thresholds
  - Include troubleshooting procedures for common issues
  - Document log analysis and correlation ID tracing
  - **Deliverable:** Complete monitoring documentation
  - _Requirements: 13.6_

- [ ] 46. Complete Phase 2 scope documentation (must-have)
  - Update docs/phase-2-scope.md explicitly stating Phase 2 scope
  - Document that Detection_Engine and Score_Engine are placeholders
  - Document that detection and scoring logic is deferred to later phases
  - Document that Identity_Collector records basic trust edges only
  - Clarify what is included vs excluded in Phase 2
  - **Deliverable:** Complete Phase 2 scope documentation
  - _Requirements: 13.7_

- [ ] 47. End-to-end pipeline verification (must-have)
  - Inject sample CloudTrail events using scripts/inject-events.py
  - Verify events flow through Event_Normalizer → Detection_Engine → Incident_Processor
  - Verify Event_Normalizer invokes Identity_Collector asynchronously
  - Verify Identity_Collector creates Identity_Profile and Trust_Relationship records
  - Verify API endpoints return correct data with pagination
  - Verify SNS notifications are sent for high-severity incidents
  - Verify CloudWatch logs, metrics, and alarms are functioning
  - **Deliverable:** Verified end-to-end event processing pipeline
  - _Requirements: 4.13, 6.9, 8.4_

- [ ]* 48. Write unit tests for Event_Normalizer (nice-to-have)
  - Test identity ARN extraction from various userIdentity formats
  - Test timestamp normalization to ISO 8601
  - Test validation error handling for missing required fields
  - Test sensitive data exclusion
  - **Deliverable:** Unit tests for Event_Normalizer
  - _Requirements: 6.1, 6.3, 6.5, 6.7_

- [ ]* 49. Write property test for Event_Normalizer round-trip consistency (nice-to-have)
  - **Property 1: Round-trip consistency**
  - **Validates: Requirements 6.11**
  - Test that normalizing → serializing → normalizing produces equivalent Event_Summary
  - Use Hypothesis to generate CloudTrail events with required fields
  - Verify idempotency of normalization process
  - **Deliverable:** Property-based test for Event_Normalizer
  - _Requirements: 6.11_

- [ ]* 50. Write unit tests for Detection_Engine placeholder (nice-to-have)
  - Test that Detection_Engine logs received events correctly
  - Test that placeholder findings have correct data structure
  - Test that Incident_Processor invocation succeeds
  - **Deliverable:** Unit tests for Detection_Engine placeholder
  - _Requirements: 7.1, 7.4_

- [ ]* 51. Write unit tests for Identity_Collector (nice-to-have)
  - Test identity type extraction from various ARN formats
  - Test account ID extraction from ARNs
  - Test Identity_Profile creation and updates
  - Test Trust_Relationship creation from AssumeRole events
  - Test identity deletion handling (marking inactive)
  - **Deliverable:** Unit tests for Identity_Collector
  - _Requirements: 8.11, 8.12, 8.15, 8.18_

- [ ]* 52. Write unit tests for Incident_Processor (nice-to-have)
  - Test incident ID generation (UUID format)
  - Test incident creation with required fields
  - Test deduplication logic (24-hour window, update existing incident)
  - Test SNS notification for high-severity incidents
  - Test status transition validation
  - **Deliverable:** Unit tests for Incident_Processor
  - _Requirements: 8.2, 8.3, 8.4, 8.7, 8.8_

- [ ]* 53. Write unit tests for Score_Engine placeholder (nice-to-have)
  - Test severity classification function with various score values
  - Test placeholder score record creation
  - Test that Score_Engine logs invocations correctly
  - **Deliverable:** Unit tests for Score_Engine placeholder
  - _Requirements: 7.7, 7.10, 7.12_

- [ ]* 54. Write unit tests for API_Handler (nice-to-have)
  - Test each endpoint with valid parameters
  - Test pagination with next_token
  - Test parameter validation and error responses
  - Test ARN URL encoding/decoding
  - Test 404 responses for missing resources
  - **Deliverable:** Unit tests for API_Handler
  - _Requirements: 9.1-9.18_

- [ ]* 55. Write integration tests for event processing pipeline (nice-to-have)
  - Test CloudTrail event → EventBridge → Event_Normalizer → DynamoDB flow
  - Test Event_Normalizer → Detection_Engine → Incident_Processor flow
  - Test Event_Normalizer → Identity_Collector → Identity_Profile flow
  - Test Incident_Processor → SNS notification flow
  - Verify end-to-end event processing with sample events
  - **Deliverable:** Integration tests for event processing pipeline
  - _Requirements: 4.13, 6.9, 8.4_

- [ ]* 56. Write integration tests for API endpoints (nice-to-have)
  - Test all GET endpoints with various query parameters
  - Test PATCH /incidents/{id} endpoint for status updates
  - Test pagination with next_token
  - Test error responses (400, 404, 500)
  - Verify response format and data consistency
  - **Deliverable:** Integration tests for API endpoints
  - _Requirements: 5.5-5.17, 9.1-9.18_

## Notes

**Priority Labels:**
- **must-have**: Critical for Phase 2 functionality (37 tasks)
- **should-have**: Important but not blocking (1 task - documentation stubs)
- **nice-to-have**: Optional enhancements (9 tasks - unit/integration tests)

**Task Organization:**
- Milestone 1: Repository Bootstrap and Foundation (3 top-level tasks)
- Milestone 2: Infrastructure Core (15 top-level tasks)
- Milestone 3: Processing Pipeline (10 top-level tasks, many with sub-tasks)
- Milestone 4: API Layer (7 top-level tasks, many with sub-tasks)
- Milestone 5: Observability and Monitoring (3 top-level tasks, each with sub-tasks)
- Milestone 6: Testing, Documentation, and Validation (19 top-level tasks)

**Key Improvements from User Feedback:**
1. Added Task 0 for repository bootstrap
2. Reordered: foundation → infra → code → docs/testing
3. Broke large tasks into smaller chunks (e.g., split incident processor into 5 sub-tasks)
4. Added priority labels (must-have, should-have, nice-to-have)
5. Created documentation stubs early (Task 2)
6. Made Terraform tasks explicitly dependency-aware
7. Clarified Event_Normalizer invocation architecture throughout
8. Fixed task 22.3 deduplication to update existing incident, not skip
9. Added notes about unsupported query combinations for API tasks (31.1, 32.1, 33)
10. Reorganized into 6 clear milestones
11. Each task has observable deliverable

**Important Architecture Notes:**
- Detection_Engine and Score_Engine are PLACEHOLDER functions (logging only)
- Identity_Collector records basic trust edges only (no complex analysis)
- Event_Normalizer invokes Identity_Collector asynchronously (NOT triggered by EventBridge directly)
- Incident deduplication updates existing incident with new event_ids (does not skip)
- Terraform resolves dependencies automatically via resource references
- Blast_Radius_Score table stores current snapshot only (overwrites on each calculation)
- Phase 2 focuses on infrastructure foundation, not business logic implementation

**Each task references specific requirements for traceability (e.g., _Requirements: 1.1, 1.2_)**
