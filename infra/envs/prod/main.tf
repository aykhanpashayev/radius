# Prod environment configuration for Radius
# This file instantiates the root module with prod-specific values

module "radius" {
  source = "../.."

  environment = "prod"
  aws_region  = "us-east-1"
  
  resource_prefix = "radius-prod"

  # Lambda configuration - higher resources for production workload
  lambda_memory = {
    event_normalizer   = 1024
    detection_engine   = 2048
    incident_processor = 1024
    identity_collector = 1024
    score_engine       = 2048
    api_handler        = 512
  }

  lambda_timeout = {
    event_normalizer   = 30
    detection_engine   = 60
    incident_processor = 30
    identity_collector = 30
    score_engine       = 60
    api_handler        = 10
  }

  # Higher concurrency for production
  lambda_concurrency_limit = 100

  # Longer log retention for prod
  log_retention_days = 30

  # Organization-wide CloudTrail for prod
  cloudtrail_organization_enabled = true

  # Enable PITR for production data protection
  enable_pitr = true

  tags = {
    CostCenter = "Production"
    Owner      = "DevOps"
    Compliance = "Required"
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
