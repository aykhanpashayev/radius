# Terraform Modules

The Radius infrastructure is composed of 8 modules under `infra/modules/`. The root module (`infra/`) wires them together. Environment-specific entry points live in `infra/envs/dev/` and `infra/envs/prod/`.

## Module Dependency Order

```
kms → dynamodb, sns
dynamodb, sns, kms → lambda
lambda → eventbridge, apigateway
kms → cloudtrail
lambda, dynamodb, sns → cloudwatch
```

Terraform resolves these automatically via resource references — no explicit `depends_on` is needed between modules.

## kms

Manages KMS keys for all services.

**Outputs:** `dynamodb_key_arn`, `lambda_key_arn`, `sns_key_arn`, `cloudtrail_key_arn`

Key rotation is enabled on all keys.

## dynamodb

Manages all 5 DynamoDB tables and their GSIs.

**Inputs:** `kms_key_arn`, `enable_pitr`, `prefix`, `environment`  
**Outputs:** `table_names` (map), `table_arns` (map), `gsi_arns` (map)

Tables: Identity_Profile, Blast_Radius_Score, Incident, Event_Summary, Trust_Relationship. See `docs/database-schema.md` for full schema.

## lambda

Manages all 6 Lambda functions, IAM roles, DLQs, and CloudWatch log groups.

**Inputs:** `function_configs` (memory), `timeout_configs`, `dynamodb_table_names`, `dynamodb_table_arns`, `dynamodb_gsi_arns`, `sns_topic_arn`, `kms_key_arn`, `lambda_s3_bucket`  
**Outputs:** `function_arns` (map), `function_names` (map), `role_arns` (map), `dlq_arns` (map)

All functions use Python 3.11 on arm64. Deployment packages are uploaded to S3 by `scripts/build-lambdas.sh`.

## eventbridge

Manages the CloudTrail management event routing rule.

**Inputs:** `lambda_function_arns.event_normalizer`  
**Outputs:** `rule_arn`, `event_bus_arn`

Filters IAM, STS, Organizations, and EC2 management events. Routes to Event_Normalizer with retry policy and DLQ.

## apigateway

Manages the REST API, all 10 endpoint operations, Lambda proxy integrations, deployment stage, and access logging.

**Inputs:** `lambda_function_arn` (API_Handler), `lambda_function_name`, `enable_logging`, `log_retention_days`  
**Outputs:** `api_endpoint`, `api_id`, `api_arn`, `execution_arn`, `stage_name`

## cloudtrail

Manages the CloudTrail trail and S3 bucket for log storage.

**Inputs:** `kms_key_arn`, `organization_enabled`  
**Outputs:** `trail_arn`, `s3_bucket_name`

Set `organization_enabled = true` in prod for org-wide coverage. Dev uses single-account trail.

S3 lifecycle: transition to Glacier after 90 days, delete after 365 days.

## sns

Manages the Alert_Topic SNS topic and subscriptions.

**Inputs:** `kms_key_arn`, `email_subscriptions`, `https_subscriptions`  
**Outputs:** `alert_topic_arn`, `alert_topic_name`

Subscriptions include severity filter policies (High, Very High, Critical only).

## cloudwatch

Manages alarms, dashboards, and log group configuration.

**Inputs:** `lambda_function_names`, `dynamodb_table_names`, `api_gateway_name`, `dlq_arns`, `alarm_sns_topic_arn`  
**Outputs:** `dashboard_names`, `alarm_arns`

Alarms: Lambda error rate >5%, Lambda duration p99, DynamoDB throttles >10/min, DLQ depth >0, API Gateway 5xx >1%.  
Dashboards: Lambda, DynamoDB, API Gateway, EventBridge.

## Environment Configuration

| Variable | Dev | Prod |
|---|---|---|
| cloudtrail_organization_enabled | false | true |
| enable_pitr | false | true |
| log_retention_days | 7 | 30 |
| lambda_concurrency_limit | 10 | null (unreserved) |

See `infra/envs/dev/terraform.tfvars` and `infra/envs/prod/terraform.tfvars` for full values.
