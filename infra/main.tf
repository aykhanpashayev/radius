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
# 2. Cognito — user pool for dashboard authentication (no dependencies)
# ---------------------------------------------------------------------------
module "cognito" {
  source = "./modules/cognito"
  prefix = local.name_prefix
  tags   = var.tags

  callback_urls = length(var.cognito_callback_urls) > 0 ? var.cognito_callback_urls : ["https://${module.frontend.domain_name}/callback", "http://localhost:5173/callback"]
  logout_urls   = length(var.cognito_logout_urls) > 0 ? var.cognito_logout_urls : ["https://${module.frontend.domain_name}/logout", "http://localhost:5173/logout"]
}

# SSM parameters — config values written here so CI/CD can read them at
# frontend build time without hardcoding anything in the repo.
resource "aws_ssm_parameter" "cognito_user_pool_id" {
  name  = "/radius/${var.environment}/cognito/user_pool_id"
  type  = "String"
  value = module.cognito.user_pool_id
}

resource "aws_ssm_parameter" "cognito_client_id" {
  name  = "/radius/${var.environment}/cognito/client_id"
  type  = "String"
  value = module.cognito.client_id
}

resource "aws_ssm_parameter" "api_endpoint" {
  name  = "/radius/${var.environment}/api/endpoint"
  type  = "String"
  value = module.apigateway.api_endpoint
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
# 3b. VPC — private subnets + endpoints (optional, no dependencies)
# ---------------------------------------------------------------------------
module "vpc" {
  count  = var.enable_vpc ? 1 : 0
  source = "./modules/vpc"

  prefix             = local.name_prefix
  environment        = var.environment
  aws_region         = var.aws_region
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  tags               = var.tags
}

# ---------------------------------------------------------------------------
# 3c. Secrets Manager — alerting webhook secrets (optional, no dependencies)
# ---------------------------------------------------------------------------
module "secrets" {
  count  = var.enable_secrets_manager ? 1 : 0
  source = "./modules/secrets"

  prefix      = local.name_prefix
  environment = var.environment
  kms_key_arn = module.kms.lambda_key_arn
  tags        = var.tags
}

# ---------------------------------------------------------------------------
# 4. Lambda — functions (depends on DynamoDB, SNS, KMS)
# ---------------------------------------------------------------------------
module "lambda" {
  source = "./modules/lambda"

  environment        = var.environment
  prefix             = local.name_prefix
  aws_region         = var.aws_region
  lambda_s3_bucket   = var.lambda_s3_bucket
  log_retention_days = var.log_retention_days

  function_configs = {
    event_normalizer   = var.lambda_memory.event_normalizer
    detection_engine   = var.lambda_memory.detection_engine
    incident_processor = var.lambda_memory.incident_processor
    identity_collector = var.lambda_memory.identity_collector
    score_engine       = var.lambda_memory.score_engine
    api_handler        = var.lambda_memory.api_handler
    remediation_engine = var.lambda_memory.remediation_engine
  }

  timeout_configs = {
    event_normalizer   = var.lambda_timeout.event_normalizer
    detection_engine   = var.lambda_timeout.detection_engine
    incident_processor = var.lambda_timeout.incident_processor
    identity_collector = var.lambda_timeout.identity_collector
    score_engine       = var.lambda_timeout.score_engine
    api_handler        = var.lambda_timeout.api_handler
    remediation_engine = var.lambda_timeout.remediation_engine
  }

  concurrency_limit     = var.lambda_concurrency_limit
  dynamodb_table_names  = module.dynamodb.table_names
  dynamodb_table_arns   = module.dynamodb.table_arns
  dynamodb_gsi_arns     = module.dynamodb.gsi_arns
  sns_topic_arn         = module.sns.alert_topic_arn
  remediation_topic_arn = module.sns.remediation_topic_arn
  kms_key_arn           = module.kms.lambda_key_arn
  dry_run               = var.remediation_dry_run
  log_level             = var.log_level
  vpc_config            = var.enable_vpc ? module.vpc[0].vpc_config : null
  secret_arns           = var.enable_secrets_manager ? module.secrets[0].secret_arns : []

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

  lambda_function_arn   = module.lambda.function_arns.api_handler
  lambda_function_name  = module.lambda.function_names.api_handler
  log_retention_days    = var.log_retention_days
  enable_logging        = false
  throttle_burst_limit  = var.api_throttle_burst_limit
  throttle_rate_limit   = var.api_throttle_rate_limit
  cognito_user_pool_arn = module.cognito.user_pool_arn

  tags = var.tags
}

# ---------------------------------------------------------------------------
# 6b. WAF — Web ACL for API Gateway (optional, depends on API Gateway)
# ---------------------------------------------------------------------------
module "waf" {
  count  = var.enable_waf ? 1 : 0
  source = "./modules/waf"

  prefix        = local.name_prefix
  environment   = var.environment
  api_stage_arn = module.apigateway.stage_arn
  rate_limit    = var.waf_rate_limit
  tags          = var.tags
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

# ---------------------------------------------------------------------------
# 8b. AWS Backup — daily snapshots of PITR-enabled DynamoDB tables (optional)
# ---------------------------------------------------------------------------
module "backup" {
  count  = var.enable_backup ? 1 : 0
  source = "./modules/backup"

  prefix      = local.name_prefix
  environment = var.environment
  aws_region  = var.aws_region
  kms_key_arn = module.kms.dynamodb_key_arn

  # Only back up the 5 PITR-enabled tables; event_summary and trust_relationship
  # are excluded because they can be rebuilt from CloudTrail.
  table_arns = [
    module.dynamodb.table_arns.identity_profile,
    module.dynamodb.table_arns.blast_radius_score,
    module.dynamodb.table_arns.incident,
    module.dynamodb.table_arns.remediation_config,
    module.dynamodb.table_arns.remediation_audit_log,
  ]

  backup_retention_days = var.backup_retention_days
  copy_to_region        = var.backup_secondary_region
  tags                  = var.tags
}

# ---------------------------------------------------------------------------
# 9. Frontend — S3 + CloudFront for the React dashboard
# ---------------------------------------------------------------------------
module "frontend" {
  source      = "./modules/frontend"
  environment = var.environment
  prefix      = local.name_prefix
  tags        = var.tags
}

# ---------------------------------------------------------------------------
# 10. GitHub Actions OIDC — allows CI/CD to assume a deploy role without
#    long-lived AWS access keys stored in GitHub Secrets.
# ---------------------------------------------------------------------------
resource "aws_iam_openid_connect_provider" "github" {
  count           = var.github_repo != "" ? 1 : 0
  url             = "https://token.actions.githubusercontent.com"
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

resource "aws_iam_role" "github_deploy" {
  count = var.github_repo != "" ? 1 : 0
  name  = "${local.name_prefix}-github-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = aws_iam_openid_connect_provider.github[0].arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringLike = {
          "token.actions.githubusercontent.com:sub" = [
            "repo:${var.github_repo}:ref:refs/heads/main",
            "repo:${var.github_repo}:ref:refs/heads/develop"
          ]
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  count = var.github_repo != "" ? 1 : 0
  name  = "${local.name_prefix}-github-deploy-policy"
  role  = aws_iam_role.github_deploy[0].name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "LambdaDeployment"
        Effect = "Allow"
        Action = [
          "lambda:CreateFunction", "lambda:UpdateFunctionCode",
          "lambda:UpdateFunctionConfiguration", "lambda:GetFunction",
          "lambda:GetFunctionConfiguration", "lambda:DeleteFunction",
          "lambda:AddPermission", "lambda:RemovePermission",
          "lambda:ListFunctions", "lambda:TagResource",
          "lambda:PutFunctionEventInvokeConfig",
          "lambda:CreateEventSourceMapping", "lambda:DeleteEventSourceMapping",
          "lambda:GetEventSourceMapping"
        ]
        Resource = "*"
      },
      {
        Sid    = "DynamoDB"
        Effect = "Allow"
        Action = [
          "dynamodb:CreateTable", "dynamodb:DeleteTable", "dynamodb:DescribeTable",
          "dynamodb:UpdateTable", "dynamodb:ListTables", "dynamodb:TagResource",
          "dynamodb:UpdateTimeToLive", "dynamodb:DescribeTimeToLive",
          "dynamodb:DescribeContinuousBackups", "dynamodb:UpdateContinuousBackups"
        ]
        Resource = "*"
      },
      {
        Sid    = "S3Artifacts"
        Effect = "Allow"
        Action = [
          "s3:PutObject", "s3:GetObject", "s3:DeleteObject",
          "s3:ListBucket", "s3:GetBucketVersioning",
          "s3:PutBucketVersioning", "s3:CreateBucket",
          "s3:PutBucketPolicy", "s3:GetBucketPolicy",
          "s3:PutBucketPublicAccessBlock", "s3:GetBucketPublicAccessBlock"
        ]
        Resource = "*"
      },
      {
        Sid    = "SNS"
        Effect = "Allow"
        Action = [
          "sns:CreateTopic", "sns:DeleteTopic", "sns:GetTopicAttributes",
          "sns:SetTopicAttributes", "sns:Subscribe", "sns:Unsubscribe",
          "sns:ListSubscriptionsByTopic", "sns:TagResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "EventBridge"
        Effect = "Allow"
        Action = [
          "events:PutRule", "events:DeleteRule", "events:DescribeRule",
          "events:PutTargets", "events:RemoveTargets", "events:ListTargetsByRule",
          "events:TagResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "APIGateway"
        Effect = "Allow"
        Action = ["apigateway:*"]
        Resource = "*"
      },
      {
        Sid    = "CloudTrail"
        Effect = "Allow"
        Action = [
          "cloudtrail:CreateTrail", "cloudtrail:DeleteTrail",
          "cloudtrail:DescribeTrails", "cloudtrail:GetTrailStatus",
          "cloudtrail:StartLogging", "cloudtrail:StopLogging",
          "cloudtrail:UpdateTrail", "cloudtrail:AddTags",
          "cloudtrail:PutEventSelectors", "cloudtrail:GetEventSelectors"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatch"
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricAlarm", "cloudwatch:DeleteAlarms",
          "cloudwatch:DescribeAlarms", "cloudwatch:PutDashboard",
          "cloudwatch:DeleteDashboards", "cloudwatch:GetDashboard",
          "logs:CreateLogGroup", "logs:DeleteLogGroup",
          "logs:PutRetentionPolicy", "logs:DescribeLogGroups",
          "logs:TagLogGroup"
        ]
        Resource = "*"
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = [
          "kms:CreateKey", "kms:DescribeKey", "kms:EnableKeyRotation",
          "kms:GetKeyPolicy", "kms:PutKeyPolicy", "kms:ScheduleKeyDeletion",
          "kms:CreateAlias", "kms:DeleteAlias", "kms:ListAliases",
          "kms:TagResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "Cognito"
        Effect = "Allow"
        Action = [
          "cognito-idp:CreateUserPool", "cognito-idp:DeleteUserPool",
          "cognito-idp:DescribeUserPool", "cognito-idp:UpdateUserPool",
          "cognito-idp:CreateUserPoolClient", "cognito-idp:DeleteUserPoolClient",
          "cognito-idp:DescribeUserPoolClient", "cognito-idp:UpdateUserPoolClient",
          "cognito-idp:CreateUserPoolDomain", "cognito-idp:DeleteUserPoolDomain"
        ]
        Resource = "*"
      },
      {
        Sid    = "SSM"
        Effect = "Allow"
        Action = [
          "ssm:PutParameter", "ssm:GetParameter", "ssm:GetParameters",
          "ssm:DeleteParameter", "ssm:AddTagsToResource"
        ]
        Resource = "*"
      },
      {
        Sid    = "IAMRolesForLambda"
        Effect = "Allow"
        Action = [
          "iam:CreateRole", "iam:DeleteRole", "iam:GetRole",
          "iam:PassRole", "iam:AttachRolePolicy", "iam:DetachRolePolicy",
          "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:GetRolePolicy",
          "iam:TagRole", "iam:CreateOpenIDConnectProvider",
          "iam:DeleteOpenIDConnectProvider", "iam:GetOpenIDConnectProvider",
          "iam:CreatePolicy", "iam:DeletePolicy", "iam:GetPolicy",
          "iam:GetPolicyVersion", "iam:CreatePolicyVersion",
          "iam:DeletePolicyVersion", "iam:ListPolicyVersions"
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudFront"
        Effect = "Allow"
        Action = [
          "cloudfront:CreateDistribution", "cloudfront:UpdateDistribution",
          "cloudfront:DeleteDistribution", "cloudfront:GetDistribution",
          "cloudfront:CreateInvalidation", "cloudfront:TagResource",
          "cloudfront:CreateOriginAccessControl",
          "cloudfront:DeleteOriginAccessControl",
          "cloudfront:GetOriginAccessControl"
        ]
        Resource = "*"
      },
      {
        Sid    = "SQSForDLQ"
        Effect = "Allow"
        Action = [
          "sqs:CreateQueue", "sqs:DeleteQueue", "sqs:GetQueueAttributes",
          "sqs:SetQueueAttributes", "sqs:TagQueue"
        ]
        Resource = "*"
      },
      {
        Sid    = "TerraformState"
        Effect = "Allow"
        Action = [
          "s3:GetObject", "s3:PutObject", "s3:DeleteObject", "s3:ListBucket",
          "dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"
        ]
        Resource = "*"
      }
    ]
  })
}

# SSM — frontend S3 bucket and CloudFront distribution ID for CI/CD deploy workflow.
resource "aws_ssm_parameter" "frontend_bucket" {
  name  = "/radius/${var.environment}/frontend/bucket"
  type  = "String"
  value = module.frontend.bucket_name
}

resource "aws_ssm_parameter" "cloudfront_distribution_id" {
  name  = "/radius/${var.environment}/cloudfront/distribution_id"
  type  = "String"
  value = module.frontend.distribution_id
}
