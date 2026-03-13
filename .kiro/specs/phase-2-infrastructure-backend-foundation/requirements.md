# Requirements Document: Phase 2 Infrastructure and Backend Foundation

## Introduction

This document specifies requirements for Phase 2 of Radius, a cloud security platform that measures and reduces the blast radius of identity-based attacks in AWS Organizations. 

**Phase 2 Scope:** This phase establishes ONLY the infrastructure foundation and service skeletons. It includes Terraform modules, Lambda function stubs with logging, EventBridge routing, DynamoDB tables with GSIs, API Gateway endpoints, and SNS alerting. 

**Explicitly Out of Scope:** Detection rules, scoring algorithms, complex analysis logic, and business intelligence. The Detection_Engine and Score_Engine are PLACEHOLDER functions that log events and pass data through. Full detection and scoring logic will be implemented in later phases.

## Glossary

- **Radius_System**: The complete cloud security platform for identity-based attack analysis
- **Infrastructure_Module**: Terraform configuration that provisions AWS resources
- **Event_Normalizer**: Lambda function that transforms CloudTrail events into standardized format
- **Detection_Engine**: Lambda function PLACEHOLDER that logs events and defines interfaces for future detection logic
- **Incident_Processor**: Lambda function that creates and manages security incidents
- **Identity_Collector**: Lambda function that gathers and maintains IAM identity profiles
- **Score_Engine**: Lambda function PLACEHOLDER that logs invocations and defines interfaces for future scoring logic
- **API_Handler**: Lambda function that processes API Gateway requests
- **Event_Router**: EventBridge rules that direct events to appropriate Lambda functions
- **Identity_Profile**: DynamoDB record containing IAM identity metadata and behavior history
- **Blast_Radius_Score**: Numeric value (0-100) estimating potential damage if identity is compromised
- **Incident**: DynamoDB record representing a security event requiring investigation
- **Event_Summary**: DynamoDB record containing normalized CloudTrail event data
- **Trust_Relationship**: DynamoDB record representing cross-account or service-to-service permissions
- **Environment**: Isolated deployment instance (dev or prod)
- **CloudTrail_Event**: AWS API activity record from CloudTrail service
- **Management_Event**: CloudTrail event representing control-plane operations
- **Alert_Topic**: SNS topic for incident notifications
- **Terraform_State**: Backend storage for Terraform infrastructure state
- **GSI**: Global Secondary Index for DynamoDB table queries


## Requirements

### Requirement 1: Terraform Module Structure and Infrastructure Foundation

**User Story:** As a DevOps engineer, I want a modular Terraform project structure with environment isolation, so that I can provision and manage AWS resources consistently across dev and prod environments.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL organize code into a root module at infra/ with environment-specific configurations at infra/envs/dev and infra/envs/prod
2. THE Infrastructure_Module SHALL organize reusable modules under infra/modules/ with service-based subdirectories: lambda (Lambda functions with IAM roles), dynamodb (DynamoDB tables with GSIs), eventbridge (EventBridge rules and event routing), apigateway (API Gateway with endpoints), cloudtrail (CloudTrail configuration and S3 storage), sns (SNS topics for alerting), cloudwatch (CloudWatch logs, metrics, alarms, dashboards), and kms (KMS keys for encryption)
3. THE Infrastructure_Module SHALL define module inputs for environment name, resource naming prefix, scaling parameters, and feature flags
4. THE Infrastructure_Module SHALL define module outputs for resource ARNs, endpoint URLs, and identifiers for cross-module references
5. THE Infrastructure_Module SHALL store Terraform_State in S3 with DynamoDB locking to prevent concurrent modifications
6. THE Infrastructure_Module SHALL define all AWS resource dependencies explicitly using Terraform resource references
7. THE Infrastructure_Module SHALL use variables for environment-specific configuration values including memory limits, timeout values, and retention periods
8. THE Infrastructure_Module SHALL isolate resources between environments using naming prefixes and separate AWS accounts or resource tagging
9. WHERE the Environment is dev, THE Infrastructure_Module SHALL use minimal resource provisioning for cost savings
10. WHERE the Environment is prod, THE Infrastructure_Module SHALL enable high availability and redundancy features
11. THE Infrastructure_Module SHALL include deployment scripts for Terraform initialization, planning, and applying with environment selection via command-line parameters
12. THE deployment script SHALL validate Terraform configuration before applying changes and display a summary of resources to be created or modified

### Requirement 2: DynamoDB Tables with Global Secondary Indexes

**User Story:** As a backend developer, I want DynamoDB tables with appropriate GSIs, so that I can efficiently query identity profiles, scores, incidents, events, and trust relationships.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL provision a DynamoDB table for Identity_Profile with identity ARN as partition key
2. THE Identity_Profile table SHALL include GSI "IdentityTypeIndex" with identity_type as partition key and account_id as sort key, using projection type ALL
3. THE Identity_Profile table SHALL include GSI "AccountIndex" with account_id as partition key and last_activity_timestamp as sort key, using projection type ALL
4. THE Identity_Profile table SHALL include fields for identity ARN, type, creation date, last activity timestamp, account ID, and tags
5. THE Infrastructure_Module SHALL provision a DynamoDB table for Blast_Radius_Score with identity ARN as partition key
6. THE Blast_Radius_Score table SHALL include GSI "ScoreRangeIndex" with severity_level as partition key and score_value as sort key, using projection type ALL
7. THE Blast_Radius_Score table SHALL include GSI "SeverityIndex" with severity_level as partition key and calculation_timestamp as sort key, using projection type KEYS_ONLY
8. THE Blast_Radius_Score table SHALL store score value (0-100), calculation timestamp, severity level (Low, Moderate, High, Very High, Critical), and contributing factors
9. THE Infrastructure_Module SHALL provision a DynamoDB table for Incident with incident ID as partition key
10. THE Incident table SHALL include GSI "StatusIndex" with status as partition key and creation_timestamp as sort key, using projection type ALL
11. THE Incident table SHALL include GSI "SeverityIndex" with severity as partition key and creation_timestamp as sort key, using projection type ALL
12. THE Incident table SHALL include GSI "IdentityIndex" with identity_arn as partition key and creation_timestamp as sort key, using projection type KEYS_ONLY
13. THE Incident table SHALL include fields for incident ID, identity ARN, detection type, severity, confidence, status, creation timestamp, update timestamp, and related event IDs
14. THE Infrastructure_Module SHALL provision a DynamoDB table for Event_Summary with composite key of identity ARN (partition) and timestamp (sort)
15. THE Event_Summary table SHALL include GSI "EventIdIndex" with event_id as partition key, using projection type ALL, to support direct event lookup by event ID for operational troubleshooting and incident investigation
16. THE Event_Summary table SHALL include GSI "EventTypeIndex" with event_type as partition key and timestamp as sort key, using projection type KEYS_ONLY
17. THE Event_Summary table SHALL include GSI "TimeRangeIndex" with date_partition as partition key and timestamp as sort key, using projection type ALL
18. THE Event_Summary table SHALL include fields for event ID, identity ARN, event type, timestamp, source IP, user agent, and relevant parameters
19. THE Infrastructure_Module SHALL provision a DynamoDB table for Trust_Relationship with composite key of source identity ARN (partition) and target resource ARN (sort)
20. THE Trust_Relationship table SHALL include GSI "RelationshipTypeIndex" with relationship_type as partition key and discovery_timestamp as sort key, using projection type ALL
21. THE Trust_Relationship table SHALL include GSI "TargetAccountIndex" with target_account_id as partition key and discovery_timestamp as sort key, using projection type KEYS_ONLY
22. THE Trust_Relationship table SHALL include fields for source identity ARN, target resource ARN, relationship type, permissions granted, discovery timestamp, and active status
23. THE Infrastructure_Module SHALL configure all DynamoDB tables with on-demand billing mode for cost efficiency
24. THE Infrastructure_Module SHALL enable point-in-time recovery for Identity_Profile, Blast_Radius_Score, and Incident tables
25. THE Infrastructure_Module SHALL enable time-to-live for Event_Summary table for automatic deletion of old events
26. THE Infrastructure_Module SHALL enable time-to-live for Incident table for automatic archival of resolved incidents
27. THE Infrastructure_Module SHALL enable encryption at rest for all DynamoDB tables using KMS

### Requirement 3: Lambda Function Infrastructure and Configuration

**User Story:** As a backend developer, I want Lambda function skeletons with proper IAM roles and configuration, so that I can implement service logic with appropriate permissions and observability.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL provision Lambda functions for Event_Normalizer, Detection_Engine, Incident_Processor, Identity_Collector, Score_Engine, and API_Handler
2. THE Infrastructure_Module SHALL configure each Lambda function with appropriate memory allocation (Event_Normalizer: 512MB, Detection_Engine: 1024MB, Incident_Processor: 512MB, Identity_Collector: 512MB, Score_Engine: 1024MB, API_Handler: 256MB)
3. THE Infrastructure_Module SHALL configure timeout values appropriate for each function type (Event_Normalizer: 30s, Detection_Engine: 60s, Incident_Processor: 30s, Identity_Collector: 30s, Score_Engine: 60s, API_Handler: 10s)
4. THE Infrastructure_Module SHALL configure concurrency limits to prevent cost overruns in dev Environment
5. THE Infrastructure_Module SHALL create IAM roles for each Lambda function with least-privilege permissions
6. THE Infrastructure_Module SHALL grant Event_Normalizer permissions to read from EventBridge, write to Event_Summary table, and invoke Detection_Engine
7. THE Infrastructure_Module SHALL grant Detection_Engine permissions to read Event_Summary table and invoke Incident_Processor (placeholder only, no detection logic in Phase 2)
8. THE Infrastructure_Module SHALL grant Incident_Processor permissions to write to Incident table and publish to Alert_Topic
9. THE Infrastructure_Module SHALL grant Identity_Collector permissions to write to Identity_Profile and Trust_Relationship tables
10. THE Infrastructure_Module SHALL grant Score_Engine permissions to read Identity_Profile table and write to Blast_Radius_Score table (placeholder only, no scoring logic in Phase 2)
11. THE Infrastructure_Module SHALL grant API_Handler permissions to read from all DynamoDB tables and write to Incident table for status updates
12. THE Infrastructure_Module SHALL configure Lambda functions with environment variables for DynamoDB table names, SNS topic ARNs, and region
13. THE Infrastructure_Module SHALL enable CloudWatch Logs for all Lambda functions with structured JSON logging
14. THE Infrastructure_Module SHALL configure log retention periods (dev: 7 days, prod: 30 days)
15. THE Infrastructure_Module SHALL configure Lambda functions with VPC access only when required for data access
16. THE Infrastructure_Module SHALL configure dead-letter queues for all event-driven Lambda functions
17. WHEN a Lambda function encounters an error, THE Lambda function SHALL log structured error details with correlation IDs to CloudWatch
18. WHEN a Lambda function encounters a transient error, THE Lambda function SHALL retry the operation with exponential backoff
19. IF a Lambda function exhausts retry attempts, THEN THE Lambda function SHALL send the failed event to the dead-letter queue


### Requirement 4: CloudTrail Configuration and Event Ingestion Pipeline

**User Story:** As a security engineer, I want CloudTrail configured to capture management events and route them through EventBridge to processing functions, so that the system receives necessary audit data for analysis.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL provision a CloudTrail trail for the AWS Organization in production environments
2. WHERE the Environment is prod, THE CloudTrail trail SHALL capture management events for all accounts in the Organization using organization-wide CloudTrail configuration
3. WHERE the Environment is dev, THE Infrastructure_Module SHALL provision a single-account CloudTrail trail for testing the event processing pipeline without multi-account complexity
4. THE CloudTrail trail SHALL deliver events to EventBridge for real-time processing
5. THE CloudTrail trail SHALL store logs in S3 for compliance and backup
6. THE CloudTrail trail SHALL enable log file validation for integrity verification
7. THE CloudTrail trail SHALL encrypt logs using KMS
8. THE Infrastructure_Module SHALL enable S3 lifecycle policies for CloudTrail log archival to reduce storage costs
9. THE Infrastructure_Module SHALL configure S3 buckets with public access blocked
10. THE Infrastructure_Module SHALL provision EventBridge rules as Event_Router to direct events to appropriate Lambda functions
11. THE Event_Router SHALL filter events to include only IAM, STS, Organizations, and EC2 management events
12. THE Event_Router SHALL deliver events with at-least-once semantics
13. WHEN a Management_Event is logged to CloudTrail, THE Event_Router SHALL forward the event to the Event_Normalizer
14. THE Infrastructure_Module SHALL grant EventBridge permission to invoke Lambda functions

### Requirement 5: API Gateway with REST Endpoints

**User Story:** As a frontend developer, I want a REST API with explicit endpoints for accessing Radius data, so that I can build the dashboard interface with proper filtering, pagination, and sorting.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL provision an API Gateway REST API with IAM authorization
2. THE API Gateway SHALL enable CORS for frontend access with appropriate allowed origins
3. THE API Gateway SHALL log all requests to CloudWatch with request/response details
4. THE Infrastructure_Module SHALL grant API Gateway permission to invoke API_Handler Lambda functions
5. THE API Gateway SHALL define endpoint GET /identities with query parameters: identity_type, account_id, limit, next_token for pagination
6. THE API Gateway SHALL define endpoint GET /identities/{arn} to retrieve a specific Identity_Profile by ARN
7. THE API Gateway SHALL define endpoint GET /scores with query parameters: severity_level, min_score, max_score, limit, next_token for pagination
8. THE API Gateway SHALL define endpoint GET /scores/{arn} to retrieve a specific Blast_Radius_Score by identity ARN
9. THE API Gateway SHALL define endpoint GET /incidents with query parameters: status, severity, identity_arn, start_date, end_date, limit, next_token for pagination
10. THE API Gateway SHALL define endpoint GET /incidents/{id} to retrieve a specific Incident by incident ID
11. THE API Gateway SHALL define endpoint PATCH /incidents/{id} to update incident status with request body containing status and optional notes
12. THE API Gateway SHALL define endpoint GET /events with query parameters: identity_arn, event_type, start_date, end_date, limit, next_token for pagination
13. THE API Gateway SHALL define endpoint GET /events/{id} to retrieve a specific Event_Summary by event ID using the EventIdIndex GSI
14. THE API Gateway SHALL define endpoint GET /trust-relationships with query parameters: source_arn, target_account_id, relationship_type, limit, next_token for pagination
15. THE API Gateway SHALL route all requests to appropriate API_Handler Lambda functions
16. THE API Gateway SHALL return responses in JSON format with consistent structure including data, metadata, and pagination tokens
17. THE API Gateway SHALL return appropriate HTTP status codes (200 for success, 400 for invalid parameters, 404 for not found, 500 for server errors)


### Requirement 6: Event Normalizer Lambda Implementation

**User Story:** As a backend developer, I want the Event Normalizer to parse CloudTrail events into standardized format, so that downstream functions receive consistent data structures.

#### Acceptance Criteria

1. WHEN the Event_Normalizer receives a CloudTrail_Event from EventBridge, THE Event_Normalizer SHALL extract identity ARN, event type, timestamp, source IP, and user agent
2. WHEN the Event_Normalizer receives a CloudTrail_Event, THE Event_Normalizer SHALL parse event-specific parameters relevant to security analysis (resource ARNs, action performed, request parameters)
3. THE Event_Normalizer SHALL validate that required fields (eventName, userIdentity, eventTime) are present in the CloudTrail_Event
4. IF a required field is missing, THEN THE Event_Normalizer SHALL log a validation error with event ID and skip the event
5. THE Event_Normalizer SHALL normalize timestamp formats to ISO 8601
6. THE Event_Normalizer SHALL normalize identity ARNs to a consistent format
7. THE Event_Normalizer SHALL exclude sensitive data and large payloads from Event_Summary to minimize storage costs
8. WHEN the Event_Normalizer completes normalization, THE Event_Normalizer SHALL store the Event_Summary in DynamoDB
9. WHEN the Event_Normalizer stores an Event_Summary, THE Event_Normalizer SHALL forward the Event_Summary to the Detection_Engine for processing
10. IF the Event_Normalizer cannot parse a CloudTrail_Event, THEN THE Event_Normalizer SHALL log the error with full event context and continue processing
11. FOR ALL valid CloudTrail_Event inputs, normalizing then serializing then normalizing SHALL produce an equivalent Event_Summary (round-trip property)

### Requirement 7: Detection Engine and Score Engine Placeholder Implementation

**User Story:** As a backend developer, I want Detection Engine and Score Engine skeletons with defined interfaces, so that detection and scoring logic can be implemented in future phases without changing infrastructure.

#### Acceptance Criteria

1. WHEN the Detection_Engine receives an Event_Summary, THE Detection_Engine SHALL log the event with event ID, identity ARN, and event type for verification
2. THE Detection_Engine SHALL define interface methods for detection rule registration including rule ID, rule name, and evaluation function signature
3. THE Detection_Engine SHALL define data structures for detection findings including identity ARN, detection type, severity, confidence, and related event IDs
4. THE Detection_Engine SHALL forward Event_Summary data to the Incident_Processor for pipeline testing (no actual detection logic in Phase 2)
5. THE Detection_Engine SHALL include placeholder methods with logging statements for future detection logic implementation
6. THE Detection_Engine SHALL NOT implement any actual detection rules or suspicious behavior analysis in Phase 2
7. WHEN the Score_Engine is invoked, THE Score_Engine SHALL log the invocation with identity ARN and timestamp for verification
8. THE Score_Engine SHALL define interface methods for score calculation rules including rule ID, rule name, and calculation function signature
9. THE Score_Engine SHALL define data structures for score storage including identity ARN, score value, severity level, calculation timestamp, and contributing factors
10. THE Score_Engine SHALL create placeholder Blast_Radius_Score records with arbitrary default values (score: 50, severity: Moderate) ONLY for testing the data pipeline and API endpoints
11. THE placeholder Blast_Radius_Score records SHALL NOT represent actual risk assessment and exist solely for infrastructure verification
12. THE Score_Engine SHALL include methods for severity classification based on score ranges (0-19: Low, 20-39: Moderate, 40-59: High, 60-79: Very High, 80-100: Critical)
13. THE Score_Engine SHALL NOT implement any actual scoring algorithms, risk analysis, or meaningful score calculations in Phase 2

### Requirement 8: Incident Processor and Identity Collector Implementation

**User Story:** As a backend developer, I want the Incident Processor to create and manage incidents and the Identity Collector to maintain identity profiles, so that security events are tracked and identity metadata is current.

#### Acceptance Criteria

1. WHEN the Incident_Processor receives a detection finding, THE Incident_Processor SHALL validate that required fields (identity ARN, detection type, severity) are present
2. WHEN the Incident_Processor receives a valid detection finding, THE Incident_Processor SHALL generate a unique incident ID using UUID format
3. WHEN the Incident_Processor creates an Incident, THE Incident_Processor SHALL store the Incident record in DynamoDB with status "open"
4. WHEN the Incident_Processor creates a high-severity Incident (High, Very High, or Critical), THE Incident_Processor SHALL publish a notification to the Alert_Topic
5. THE incident notification SHALL include incident ID, identity ARN, detection type, severity, confidence, and dashboard link
6. WHERE the incident severity is Critical or Very High, THE Incident_Processor SHALL publish the notification immediately without batching
7. THE Incident_Processor SHALL prevent duplicate incidents for the same identity ARN and detection type within a 24-hour time window
8. THE Incident_Processor SHALL support incident status transitions: open → investigating → resolved, open → false_positive
9. WHEN the Incident_Processor updates an incident status, THE Incident_Processor SHALL record the update timestamp and preserve status history
10. WHEN the Identity_Collector receives identity metadata from CloudTrail events, THE Identity_Collector SHALL create or update the Identity_Profile in DynamoDB
11. THE Identity_Collector SHALL extract identity type (IAMUser, AssumedRole, AWSService) from the identity ARN
12. THE Identity_Collector SHALL extract account ID from the identity ARN using standard ARN parsing
13. THE Identity_Collector SHALL update the last_activity_timestamp field whenever identity activity is observed
14. THE Identity_Collector SHALL store identity tags when available in CloudTrail event metadata
15. WHEN the Identity_Collector observes an AssumeRole event, THE Identity_Collector SHALL create a Trust_Relationship record with source identity ARN and target role ARN
16. THE Identity_Collector SHALL record only basic trust edges (source ARN to target ARN) without performing relationship analysis, graph traversal, or permission evaluation
17. THE Identity_Collector SHALL NOT analyze trust relationship risk, calculate transitive permissions, or perform complex relationship analysis in Phase 2
18. WHEN the Identity_Collector detects identity deletion events, THE Identity_Collector SHALL mark the Identity_Profile as inactive rather than deleting the record

### Requirement 9: API Handler Implementation

**User Story:** As a backend developer, I want API Handlers to serve data to the frontend with proper validation, pagination, and error handling, so that the dashboard can display security insights reliably.

#### Acceptance Criteria

1. WHEN the API_Handler receives a GET /identities request, THE API_Handler SHALL query the Identity_Profile table using appropriate GSI based on query parameters
2. WHEN the API_Handler receives a GET /identities/{arn} request, THE API_Handler SHALL retrieve the specific Identity_Profile by partition key
3. WHEN the API_Handler receives a GET /scores request, THE API_Handler SHALL query the Blast_Radius_Score table using ScoreRangeIndex or SeverityIndex based on filters
4. WHEN the API_Handler receives a GET /scores/{arn} request, THE API_Handler SHALL retrieve the specific Blast_Radius_Score by partition key
5. WHEN the API_Handler receives a GET /incidents request, THE API_Handler SHALL query the Incident table using StatusIndex or SeverityIndex based on filters
6. WHEN the API_Handler receives a GET /incidents/{id} request, THE API_Handler SHALL retrieve the specific Incident by partition key
7. WHEN the API_Handler receives a PATCH /incidents/{id} request, THE API_Handler SHALL update the incident status and record the update timestamp
8. WHEN the API_Handler receives a GET /events request, THE API_Handler SHALL query the Event_Summary table using EventTypeIndex or TimeRangeIndex based on filters
9. WHEN the API_Handler receives a GET /events/{id} request, THE API_Handler SHALL retrieve the specific Event_Summary by querying the EventIdIndex GSI with event_id as the partition key
10. WHEN the API_Handler receives a GET /trust-relationships request, THE API_Handler SHALL query the Trust_Relationship table using appropriate GSI
11. THE API_Handler SHALL validate query parameters before executing DynamoDB queries including data type validation and range checks
12. THE API_Handler SHALL implement pagination using DynamoDB LastEvaluatedKey and return next_token in response metadata
13. THE API_Handler SHALL limit result sets to maximum 100 items per request with default limit of 25
14. THE API_Handler SHALL return responses in JSON format with structure: {data: [...], metadata: {count, next_token, query_time}}
15. IF the API_Handler encounters a DynamoDB error, THEN THE API_Handler SHALL return a 500 status code with error message
16. IF the API_Handler receives invalid parameters, THEN THE API_Handler SHALL return a 400 status code with validation details
17. IF the API_Handler cannot find a requested resource, THEN THE API_Handler SHALL return a 404 status code
18. THE API_Handler SHALL log all requests with correlation ID, endpoint, parameters, and response time


### Requirement 10: SNS Alerting Infrastructure

**User Story:** As a security operations team member, I want notifications when high-severity incidents are created, so that I can respond quickly to threats.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL provision an SNS Alert_Topic for incident notifications
2. THE Infrastructure_Module SHALL configure the Alert_Topic with email subscription endpoints for security team distribution lists
3. THE Infrastructure_Module SHALL configure the Alert_Topic with HTTPS webhook subscription endpoints for integration with external alerting systems
4. THE Infrastructure_Module SHALL enable encryption at rest for SNS messages using KMS
5. THE Alert_Topic SHALL support message attributes for filtering by severity level
6. THE incident notification message SHALL include incident ID, identity ARN, detection type, severity, confidence score, and creation timestamp
7. THE incident notification message SHALL include a direct link to the dashboard incident detail page
8. THE incident notification message SHALL format severity levels with clear visual indicators in the subject line

### Requirement 11: Monitoring, Observability, and Alerting

**User Story:** As a DevOps engineer, I want comprehensive monitoring and alerting configured, so that I can troubleshoot issues, track system health, and respond to operational problems.

#### Acceptance Criteria

1. THE Infrastructure_Module SHALL create CloudWatch log groups for all Lambda functions with structured JSON logging format
2. THE Infrastructure_Module SHALL configure log retention periods based on environment (dev: 7 days, prod: 30 days)
3. THE Infrastructure_Module SHALL create CloudWatch metrics for Lambda invocations, errors, duration, and throttles
4. THE Infrastructure_Module SHALL create CloudWatch metrics for DynamoDB consumed read/write capacity and throttled requests
5. THE Infrastructure_Module SHALL create CloudWatch metrics for API Gateway request count, latency, 4xx errors, and 5xx errors
6. THE Infrastructure_Module SHALL create CloudWatch alarms for Lambda error rates exceeding 5% over 5-minute periods
7. THE Infrastructure_Module SHALL create CloudWatch alarms for Lambda duration approaching timeout thresholds
8. THE Infrastructure_Module SHALL create CloudWatch alarms for DynamoDB throttled requests exceeding 10 per minute
9. THE Infrastructure_Module SHALL create CloudWatch alarms for dead-letter queue message counts exceeding 0
10. THE Infrastructure_Module SHALL create CloudWatch alarms for API Gateway 5xx error rates exceeding 1% over 5-minute periods
11. THE Infrastructure_Module SHALL create CloudWatch dashboards showing key system metrics including Lambda invocations, DynamoDB operations, API Gateway requests, and error rates
12. THE Infrastructure_Module SHALL configure CloudWatch alarm actions to publish to SNS topics for operational notifications
13. WHEN a Lambda function logs an error, THE Lambda function SHALL include correlation ID, function name, error type, error message, and stack trace
14. THE Lambda function SHALL include correlation IDs in all log entries for request tracing across services

### Requirement 12: Testing Infrastructure and Sample Data

**User Story:** As a backend developer, I want sample CloudTrail events and injection scripts, so that I can verify Lambda functions process events correctly and test the complete pipeline.

#### Acceptance Criteria

1. THE Radius_System SHALL include sample CloudTrail_Event JSON files in sample-data/ directory for common IAM operations (CreateUser, AttachUserPolicy, AssumeRole, CreateAccessKey)
2. THE sample events SHALL include examples of STS operations (AssumeRole, GetSessionToken, GetFederationToken)
3. THE sample events SHALL include examples of Organizations operations (CreateAccount, InviteAccountToOrganization)
4. THE sample events SHALL include examples of EC2 operations relevant to identity analysis (RunInstances with IAM instance profiles)
5. THE sample events SHALL include examples of suspicious activities for detection testing (privilege escalation patterns, unusual cross-account access)
6. THE sample events SHALL include examples of normal activities for false positive testing (routine administrative operations)
7. THE Radius_System SHALL include a Python script at scripts/inject-events.py to inject sample events into EventBridge
8. THE injection script SHALL support injecting events into dev Environment only in Phase 2
9. THE injection script SHALL support injecting individual event files or entire directories
10. THE injection script SHALL log injection results including event count, success count, and failure count
11. THE injection script SHALL validate event JSON structure before injection


### Requirement 13: Documentation and Architecture Artifacts

**User Story:** As a developer, I want comprehensive architecture documentation, so that I can understand the system design, deployment procedures, and troubleshooting approaches.

#### Acceptance Criteria

1. THE Radius_System SHALL include documentation at docs/architecture.md describing the event processing pipeline with data flow diagrams
2. THE Radius_System SHALL include documentation at docs/database-schema.md describing the DynamoDB schema for each table including primary keys, GSIs, and field definitions
3. THE Radius_System SHALL include documentation at docs/api-reference.md describing all API endpoints with HTTP methods, request parameters, response formats, and example requests/responses
4. THE Radius_System SHALL include documentation at docs/terraform-modules.md describing the Terraform module structure, module inputs/outputs, and composition patterns
5. THE Radius_System SHALL include documentation at docs/deployment.md describing deployment procedures for each Environment including prerequisites, deployment steps, and verification procedures
6. THE Radius_System SHALL include documentation at docs/monitoring.md describing monitoring dashboards, alarm configurations, and troubleshooting procedures for common issues
7. THE Radius_System SHALL include documentation at docs/phase-2-scope.md explicitly stating that Phase 2 includes only infrastructure and service skeletons, with detection and scoring logic deferred to later phases
8. THE documentation SHALL include diagrams showing Lambda function interactions, EventBridge routing, and DynamoDB access patterns
