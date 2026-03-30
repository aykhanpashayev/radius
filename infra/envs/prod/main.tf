# Prod environment entry point for Radius.
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
  frontend_s3_bucket              = var.frontend_s3_bucket
  cloudfront_distribution_id      = var.cloudfront_distribution_id
}

# ---------------------------------------------------------------------------
# Pass-through variables (values come from terraform.tfvars)
# ---------------------------------------------------------------------------
variable "environment"                     { type = string }
variable "aws_region"                      { type = string }
variable "resource_prefix"                 { type = string }
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
variable "lambda_s3_bucket"                { type = string; default = "" }
variable "email_subscriptions"             { type = list(string); default = [] }
variable "https_subscriptions"             { type = list(string); default = [] }
variable "tags"                            { type = map(string) }
variable "score_engine_schedule"           { type = string; default = "rate(6 hours)" }
variable "remediation_dry_run"             { type = bool; default = false }
variable "log_level"                       { type = string; default = "INFO" }
variable "api_throttle_burst_limit"        { type = number; default = 200 }
variable "api_throttle_rate_limit"         { type = number; default = 100 }
variable "cognito_callback_urls"           { type = list(string) }
variable "cognito_logout_urls"             { type = list(string) }
variable "github_repo"                     { type = string }
variable "frontend_s3_bucket"              { type = string; default = "" }
variable "cloudfront_distribution_id"      { type = string; default = "" }

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
