# Dev environment configuration for Radius
# This file instantiates the root module with dev-specific values

module "radius" {
  source = "../.."

  environment = "dev"
  aws_region  = "us-east-1"
  
  resource_prefix = "radius-dev"

  # Lambda configuration - minimal resources for cost savings
  lambda_memory = {
    event_normalizer   = 512
    detection_engine   = 1024
    incident_processor = 512
    identity_collector = 512
    score_engine       = 1024
    api_handler        = 256
  }

  lambda_timeout = {
    event_normalizer   = 30
    detection_engine   = 60
    incident_processor = 30
    identity_collector = 30
    score_engine       = 60
    api_handler        = 10
  }

  # Concurrency limits for cost control
  lambda_concurrency_limit = 10

  # Short log retention for dev
  log_retention_days = 7

  # Single-account CloudTrail for dev
  cloudtrail_organization_enabled = false

  # Disable PITR for dev to reduce costs
  enable_pitr = false

  tags = {
    CostCenter = "Development"
    Owner      = "DevOps"
  }
}

# Outputs
output "environment" {
  description = "Deployment environment"
  value       = module.radius.environment
}

output "aws_region" {
  description = "AWS region"
  value       = module.radius.aws_region
}

output "resource_prefix" {
  description = "Resource naming prefix"
  value       = module.radius.resource_prefix
}
