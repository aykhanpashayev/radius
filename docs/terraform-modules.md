# Terraform Modules

The Radius infrastructure is composed of 14 modules under `infra/modules/`. The root module (`infra/`) wires them together. Environment-specific entry points live in `infra/envs/dev/` and `infra/envs/prod/`.

## Module Dependency Order

```
kms, cognito → dynamodb, sns
dynamodb, sns, kms → lambda
lambda, cognito → eventbridge, apigateway
kms → cloudtrail
lambda, dynamodb, sns → cloudwatch
apigateway → waf (optional)
lambda → vpc (optional)
dynamodb → backup (optional)
cognito → frontend
```

Terraform resolves these automatically via resource references — no explicit `depends_on` is needed between modules.

## kms

Manages KMS keys for all services.

**Outputs:** `dynamodb_key_arn`, `lambda_key_arn`, `sns_key_arn`, `cloudtrail_key_arn`

Key rotation is enabled on all keys.

## cognito

Manages the Cognito User Pool, App Client, and hosted domain used to authenticate dashboard users.

**Inputs:** `prefix`, `callback_urls`, `logout_urls`, `tags`  
**Outputs:** `user_pool_id`, `user_pool_arn`, `client_id`, `domain`

Admin-only user creation — no self-registration. Tokens are valid for 1 hour (access/ID) and 7 days (refresh). The App Client is configured for the Authorization Code flow with SRP auth.

## dynamodb

Manages all 7 DynamoDB tables and their GSIs.

**Inputs:** `kms_key_arn`, `enable_pitr`, `prefix`, `environment`  
**Outputs:** `table_names` (map), `table_arns` (map), `gsi_arns` (map)

Tables: Identity_Profile, Blast_Radius_Score, Incident, Event_Summary, Trust_Relationship, Remediation_Config, Remediation_Audit_Log. See `docs/database-schema.md` for full schema.

PITR is enabled by default (`enable_pitr = true`).

## sns

Manages the Alert_Topic and Remediation_Topic SNS topics and their subscriptions.

**Inputs:** `kms_key_arn`, `email_subscriptions`, `https_subscriptions`  
**Outputs:** `alert_topic_arn`, `alert_topic_name`, `remediation_topic_arn`

Alert_Topic subscriptions include severity filter policies (High, Very High, Critical only). Remediation_Topic is used by Remediation_Engine for `alert` and `enforce` mode notifications.

## lambda

Manages all 7 Lambda functions, IAM roles, DLQs, and CloudWatch log groups.

**Inputs:** `function_configs` (memory per function), `timeout_configs`, `dynamodb_table_names`, `dynamodb_table_arns`, `dynamodb_gsi_arns`, `sns_topic_arn`, `kms_key_arn`, `lambda_s3_bucket`, `dry_run`, `log_level`  
**Outputs:** `function_arns` (map), `function_names` (map), `role_arns` (map), `dlq_arns` (map)

All functions use Python 3.11 on arm64. Every function receives `LOG_LEVEL` and `ENVIRONMENT` as environment variables. `remediation_engine` additionally receives `DRY_RUN` (controlled via `var.remediation_dry_run`). Deployment packages are uploaded to S3 by `scripts/build-lambdas.sh`.

## apigateway

Manages the REST API, all endpoint operations, Lambda proxy integrations, deployment stage, Cognito authorizer, usage plan, and throttle settings.

**Inputs:** `lambda_function_arn`, `lambda_function_name`, `cognito_user_pool_arn`, `cors_allowed_origins`, `throttle_burst_limit`, `throttle_rate_limit`, `enable_logging`, `log_retention_days`  
**Outputs:** `api_endpoint`, `api_id`, `api_arn`, `execution_arn`, `stage_name`

All non-OPTIONS methods require a valid Cognito JWT in the `Authorization` header (`COGNITO_USER_POOLS` authorizer). OPTIONS methods remain unauthenticated for CORS preflight. Throttling is enforced at both the stage level and via a usage plan. CORS `Allow-Origin` is driven by `var.cors_allowed_origins` — not hardcoded.

**Note:** API Gateway access logging is disabled by default (`enable_logging = false`). Enable it in production by setting `enable_logging = true` in `terraform.tfvars`.

## eventbridge

Manages the CloudTrail management event routing rule and the Score_Engine schedule.

**Inputs:** `lambda_function_arns.event_normalizer`  
**Outputs:** `rule_arn`, `event_bus_arn`

Filters IAM, STS, Organizations, and EC2 management events. Routes to Event_Normalizer with retry policy and DLQ.

## cloudtrail

Manages the CloudTrail trail and S3 bucket for log storage.

**Inputs:** `kms_key_arn`, `organization_enabled`  
**Outputs:** `trail_arn`, `s3_bucket_name`

Set `cloudtrail_organization_enabled = true` in prod for org-wide coverage. Dev uses single-account trail.

S3 lifecycle: transition to Glacier after 90 days, delete after 365 days.

## cloudwatch

Manages alarms, dashboards, and log group configuration.

**Inputs:** `lambda_function_names`, `dynamodb_table_names`, `api_gateway_name`, `dlq_arns`, `alarm_sns_topic_arn`  
**Outputs:** `dashboard_names`, `alarm_arns`

Alarms: Lambda error rate >5%, Lambda duration p99, DynamoDB throttles >10/min, DLQ depth >0, API Gateway 5xx >1%.  
Dashboards: Lambda, DynamoDB, API Gateway, EventBridge.

## frontend

Manages the S3 bucket and CloudFront distribution for the React dashboard.

**Inputs:** `prefix`, `environment`, `cognito_callback_urls`, `tags`  
**Outputs:** `bucket_name`, `distribution_id`, `cloudfront_domain`

S3 bucket is fully private — no public access. CloudFront uses Origin Access Control (OAC) for S3 access and enforces HTTPS. Supports SPA routing (404 → index.html redirect).

## waf _(optional)_

Manages a WAF v2 Web ACL attached to the API Gateway stage (regional scope).

**Inputs:** `api_gateway_arn`, `prefix`, `rate_limit`, `tags`  
**Outputs:** `web_acl_arn`, `web_acl_id`

Includes AWS Managed Rule Groups: Common Rule Set, Known Bad Inputs, IP Reputation List. IP rate limiting is configurable (default 300 requests per 5 minutes). Rules start in COUNT mode — observe in CloudWatch before switching to BLOCK.

Enabled via `enable_waf = true` in `terraform.tfvars`. Disabled by default.

## vpc _(optional)_

Manages a VPC with private subnets and VPC endpoints for Lambda isolation.

**Inputs:** `prefix`, `cidr_block`, `environment`, `tags`  
**Outputs:** `vpc_id`, `private_subnet_ids`, `security_group_id`

Lambda functions run in private subnets with no internet egress. AWS services (DynamoDB, SNS, S3, Lambda, SSM, CloudWatch) are reached via VPC Interface or Gateway endpoints — no NAT gateway needed. Estimated cost: ~$35/month for 5 Interface endpoints.

Enabled via `enable_vpc = true` in `terraform.tfvars`. Disabled by default.

## secrets _(optional)_

Manages Secrets Manager secrets for external alert webhook integrations (PagerDuty, OpsGenie).

**Inputs:** `prefix`, `environment`, `tags`  
**Outputs:** `secret_arns` (map)

Secret values are populated out-of-band — never stored in Terraform state or git. Lambda IAM roles are pre-granted `secretsmanager:GetSecretValue` on these ARNs.

Enabled via `enable_secrets_manager = true` in `terraform.tfvars`. Only needed if integrating with external alerting services.

## backup _(optional)_

Manages AWS Backup vaults and plans for daily DynamoDB snapshots.

**Inputs:** `table_arns`, `backup_retention_days`, `secondary_region`, `prefix`, `tags`  
**Outputs:** `vault_arn`, `plan_id`

Backs up the 5 PITR-enabled tables (identity_profile, blast_radius_score, incident, remediation_config, remediation_audit_log). Supplements (does not replace) DynamoDB PITR — provides longer retention and cross-region copy for disaster recovery. Default retention: 35 days.

Enabled via `enable_backup = true` in `terraform.tfvars`. Disabled by default.

## organizations _(optional, management account only)_

Manages AWS Organizations bootstrap resources for org-wide Radius deployment.

**Deployed separately** from the main application — requires management account credentials and its own workspace (`infra/envs/org/`). Deploy once before the first prod deployment if using org-wide CloudTrail.

Provisions: Service Control Policies (prevent CloudTrail disable / org leave), GuardDuty delegated admin designation, GuardDuty org-wide auto-enable.

---

## Environment Configuration

| Variable | Dev | Prod |
|---|---|---|
| `cloudtrail_organization_enabled` | `false` | `false` (set `true` for org-wide) |
| `enable_pitr` | `true` | `true` |
| `log_retention_days` | `7` | `365` |
| `lambda_concurrency_limit` | `0` (unreserved) | `0` (unreserved) |
| `remediation_dry_run` | `true` | `false` |
| `enable_waf` | `false` | `false` (recommended: `true`) |
| `enable_vpc` | `false` | `false` (recommended: `true`) |
| `enable_backup` | `false` | `false` (recommended: `true`) |

See `infra/envs/dev/terraform.tfvars.example` and `infra/envs/prod/terraform.tfvars.example` for full values.
