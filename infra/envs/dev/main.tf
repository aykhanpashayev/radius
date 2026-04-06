# Dev environment entry point for Radius.
# Run: terraform init -backend-config=backend.tfvars
#      terraform apply -var-file=terraform.tfvars

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    # Values supplied via backend.tfvars at init time
  }
}

module "radius" {
  source = "../.."

  environment                     = var.environment
  aws_region                      = var.aws_region
  resource_prefix                 = var.resource_prefix
  lambda_memory                   = var.lambda_memory
  lambda_timeout                  = var.lambda_timeout
  lambda_concurrency_limit        = var.lambda_concurrency_limit
  log_retention_days              = var.log_retention_days
  cloudtrail_organization_enabled = var.cloudtrail_organization_enabled
  enable_pitr                     = var.enable_pitr
  lambda_s3_bucket                = var.lambda_s3_bucket
  email_subscriptions             = var.email_subscriptions
  https_subscriptions             = var.https_subscriptions
  tags                            = var.tags
  score_engine_schedule           = var.score_engine_schedule
  remediation_dry_run             = var.remediation_dry_run
  log_level                       = var.log_level
  api_throttle_burst_limit        = var.api_throttle_burst_limit
  api_throttle_rate_limit         = var.api_throttle_rate_limit
  cognito_callback_urls           = var.cognito_callback_urls
  cognito_logout_urls             = var.cognito_logout_urls
  github_repo                     = var.github_repo
  enable_waf                      = var.enable_waf
  waf_rate_limit                  = var.waf_rate_limit
  enable_vpc                      = var.enable_vpc
  vpc_cidr                        = var.vpc_cidr
  availability_zones              = var.availability_zones
  enable_secrets_manager          = var.enable_secrets_manager
  enable_backup                   = var.enable_backup
  backup_retention_days           = var.backup_retention_days
  backup_secondary_region         = var.backup_secondary_region
}

# ---------------------------------------------------------------------------
# Pass-through variables (values come from terraform.tfvars)
# ---------------------------------------------------------------------------
variable "environment" { type = string }
variable "aws_region"  { type = string }
variable "resource_prefix" { type = string }

variable "lambda_memory" {
  type = object({
    event_normalizer   = number
    detection_engine   = number
    incident_processor = number
    identity_collector = number
    score_engine       = number
    api_handler        = number
    remediation_engine = number
  })
}

variable "lambda_timeout" {
  type = object({
    event_normalizer   = number
    detection_engine   = number
    incident_processor = number
    identity_collector = number
    score_engine       = number
    api_handler        = number
    remediation_engine = number
  })
}

variable "lambda_concurrency_limit"        { type = number }
variable "log_retention_days"              { type = number }
variable "cloudtrail_organization_enabled" { type = bool }
variable "enable_pitr"                     { type = bool }

variable "lambda_s3_bucket" {
  type    = string
  default = ""
}

variable "email_subscriptions" {
  type    = list(string)
  default = []
}

variable "https_subscriptions" {
  type    = list(string)
  default = []
}

variable "tags" { type = map(string) }

variable "score_engine_schedule" {
  type    = string
  default = "rate(24 hours)"
}

variable "remediation_dry_run" {
  type    = bool
  default = true
}

variable "log_level" {
  type    = string
  default = "INFO"
}

variable "api_throttle_burst_limit" {
  type    = number
  default = 50
}

variable "api_throttle_rate_limit" {
  type    = number
  default = 25
}

variable "cognito_callback_urls" {
  type    = list(string)
  default = ["http://localhost:5173/callback"]
}

variable "cognito_logout_urls" {
  type    = list(string)
  default = ["http://localhost:5173/logout"]
}

variable "github_repo" {
  type    = string
  default = "YOUR_ORG/radius"
}

variable "enable_waf" {
  type    = bool
  default = false
}

variable "waf_rate_limit" {
  type    = number
  default = 300
}

variable "enable_vpc" {
  type    = bool
  default = false
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "availability_zones" {
  type    = list(string)
  default = ["us-east-1a", "us-east-1b"]
}

variable "enable_secrets_manager" {
  type    = bool
  default = false
}

variable "enable_backup" {
  type    = bool
  default = false
}

variable "backup_retention_days" {
  type    = number
  default = 35
}

variable "backup_secondary_region" {
  type    = string
  default = ""
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "environment"          { value = module.radius.environment }
output "aws_region"           { value = module.radius.aws_region }
output "resource_prefix"      { value = module.radius.resource_prefix }
output "api_endpoint"         { value = module.radius.api_endpoint }
output "cognito_user_pool_id" { value = module.radius.cognito_user_pool_id }
output "cognito_client_id"    { value = module.radius.cognito_client_id }
output "cognito_domain"       { value = module.radius.cognito_domain }
