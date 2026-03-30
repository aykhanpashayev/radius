# Root Terraform module for Radius infrastructure.
# Composes all service modules with correct dependency ordering:
# KMS → DynamoDB/SNS → Lambda → EventBridge/APIGateway → CloudTrail → CloudWatch

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = merge(
      {
        Project     = "Radius"
        Environment = var.environment
        ManagedBy   = "Terraform"
      },
      var.tags
    )
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
  name_prefix = "${var.resource_prefix}-${var.environment}"
}

# ---------------------------------------------------------------------------
# 1. KMS — encryption keys (no dependencies)
# ---------------------------------------------------------------------------
module "kms" {
  source      = "./modules/kms"
  environment = var.environment
  prefix      = local.name_prefix
  tags        = var.tags
}

# ---------------------------------------------------------------------------
# 2. DynamoDB — tables (depends on KMS)
# ---------------------------------------------------------------------------
module "dynamodb" {
  source      = "./modules/dynamodb"
  environment = var.environment
  prefix      = local.name_prefix
  kms_key_arn = module.kms.dynamodb_key_arn
  enable_pitr = var.enable_pitr
  tags        = var.tags
}

# ---------------------------------------------------------------------------
# 3. SNS — alert topic (depends on KMS)
# ---------------------------------------------------------------------------
module "sns" {
  source              = "./modules/sns"
  environment         = var.environment
  prefix              = local.name_prefix
  kms_key_arn         = module.kms.sns_key_arn
  email_subscriptions = var.email_subscriptions
  https_subscriptions = var.https_subscriptions
  tags                = var.tags
}

# ---------------------------------------------------------------------------
# 4. Lambda — functions (depends on DynamoDB, SNS, KMS)
# ---------------------------------------------------------------------------
module "lambda" {
  source = "./modules/lambda"

  environment       = var.environment
  prefix            = local.name_prefix
  aws_region        = var.aws_region
  lambda_s3_bucket  = var.lambda_s3_bucket
  log_retention_days = var.log_retention_days

  function_configs = {
    event_normalizer   = var.lambda_memory.event_normalizer
    detection_engine   = var.lambda_memory.detection_engine
    incident_processor = var.lambda_memory.incident_processor
    identity_collector = var.lambda_memory.identity_collector
    score_engine       = var.lambda_memory.score_engine
    api_handler        = var.lambda_memory.api_handler
  }

  timeout_configs = {
    event_normalizer   = var.lambda_timeout.event_normalizer
    detection_engine   = var.lambda_timeout.detection_engine
    incident_processor = var.lambda_timeout.incident_processor
    identity_collector = var.lambda_timeout.identity_collector
    score_engine       = var.lambda_timeout.score_engine
    api_handler        = var.lambda_timeout.api_handler
  }

  concurrency_limit    = var.lambda_concurrency_limit
  dynamodb_table_names = module.dynamodb.table_names
  dynamodb_table_arns  = module.dynamodb.table_arns
  dynamodb_gsi_arns    = module.dynamodb.gsi_arns
  sns_topic_arn        = module.sns.alert_topic_arn
  remediation_topic_arn = module.sns.remediation_topic_arn
  kms_key_arn          = module.kms.lambda_key_arn
  dry_run              = var.remediation_dry_run

  tags = var.tags
}

# ---------------------------------------------------------------------------
# 5. EventBridge — routing rules (depends on Lambda)
# ---------------------------------------------------------------------------
module "eventbridge" {
  source      = "./modules/eventbridge"
  environment = var.environment
  prefix      = local.name_prefix

  lambda_function_arns = {
    event_normalizer = module.lambda.function_arns.event_normalizer
  }

  score_engine_schedule     = var.score_engine_schedule
  score_engine_function_arn = module.lambda.function_arns.score_engine

  tags = var.tags
}

# ---------------------------------------------------------------------------
# 6. API Gateway — REST API (depends on Lambda)
# ---------------------------------------------------------------------------
module "apigateway" {
  source      = "./modules/apigateway"
  environment = var.environment
  prefix      = local.name_prefix

  lambda_function_arn  = module.lambda.function_arns.api_handler
  lambda_function_name = module.lambda.function_names.api_handler
  log_retention_days   = var.log_retention_days
  enable_logging       = false

  tags = var.tags
}

# ---------------------------------------------------------------------------
# 7. CloudTrail — trail + S3 (depends on KMS)
# ---------------------------------------------------------------------------
module "cloudtrail" {
  source      = "./modules/cloudtrail"
  environment = var.environment
  prefix      = local.name_prefix

  kms_key_arn          = module.kms.cloudtrail_key_arn
  organization_enabled = var.cloudtrail_organization_enabled

  tags = var.tags
}

# ---------------------------------------------------------------------------
# 8. CloudWatch — alarms + dashboards (depends on all resource names/ARNs)
# ---------------------------------------------------------------------------
module "cloudwatch" {
  source      = "./modules/cloudwatch"
  environment = var.environment
  prefix      = local.name_prefix

  aws_region            = var.aws_region
  log_retention_days    = var.log_retention_days
  lambda_function_names = module.lambda.function_names
  dynamodb_table_names  = module.dynamodb.table_names
  api_gateway_name      = "${local.name_prefix}-api"
  dlq_arns              = module.lambda.dlq_arns
  alarm_sns_topic_arn   = module.sns.alert_topic_arn

  tags = var.tags
}
