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
}

# ---------------------------------------------------------------------------
# Pass-through variables (values come from terraform.tfvars)
# ---------------------------------------------------------------------------
variable "environment"                     { type = string }
variable "aws_region"                      { type = string }
variable "resource_prefix"                 { type = string }
variable "lambda_memory"                   { type = map(number) }
variable "lambda_timeout"                  { type = map(number) }
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
variable "tags"                            { type = map(string) }

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "environment"     { value = module.radius.environment }
output "aws_region"      { value = module.radius.aws_region }
output "resource_prefix" { value = module.radius.resource_prefix }
output "api_endpoint"    { value = module.radius.api_endpoint }
