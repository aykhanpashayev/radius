# Root Terraform module for Radius infrastructure
# This file composes all service modules and manages cross-module dependencies

# Configure AWS provider
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

# Data sources
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

# Local values for resource naming and configuration
locals {
  account_id      = data.aws_caller_identity.current.account_id
  region          = data.aws_region.current.name
  name_prefix     = "${var.resource_prefix}-${var.environment}"
  
  common_tags = {
    Project     = "Radius"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Module instantiations will be added as modules are implemented
# Example structure:
#
# module "kms" {
#   source      = "./modules/kms"
#   environment = var.environment
#   prefix      = local.name_prefix
#   tags        = local.common_tags
# }
#
# module "dynamodb" {
#   source      = "./modules/dynamodb"
#   environment = var.environment
#   prefix      = local.name_prefix
#   kms_key_arn = module.kms.dynamodb_key_arn
#   enable_pitr = var.enable_pitr
#   tags        = local.common_tags
# }
#
# module "lambda" {
#   source                = "./modules/lambda"
#   environment           = var.environment
#   prefix                = local.name_prefix
#   function_configs      = var.lambda_memory
#   timeout_configs       = var.lambda_timeout
#   concurrency_limit     = var.lambda_concurrency_limit
#   dynamodb_table_names  = module.dynamodb.table_names
#   sns_topic_arn         = module.sns.alert_topic_arn
#   kms_key_arn           = module.kms.lambda_key_arn
#   log_retention_days    = var.log_retention_days
#   tags                  = local.common_tags
# }
