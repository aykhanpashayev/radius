# Dev environment configuration for Radius
# Copy this file and fill in the values marked with <REPLACE>

environment     = "dev"
aws_region      = "us-east-1"
resource_prefix = "radius"

# S3 bucket where Lambda zip packages are uploaded by build-lambdas.sh
# Create this bucket before running deploy-infra.sh
# Example: "my-company-radius-artifacts-dev"
lambda_s3_bucket = "<REPLACE: your S3 bucket name>"

# Lambda memory (MB) — these defaults work for dev
lambda_memory = {
  event_normalizer   = 512
  detection_engine   = 1024
  incident_processor = 512
  identity_collector = 512
  score_engine       = 1024
  api_handler        = 256
  remediation_engine = 512
}

# Lambda timeouts (seconds)
lambda_timeout = {
  event_normalizer   = 30
  detection_engine   = 60
  incident_processor = 30
  identity_collector = 30
  score_engine       = 60
  api_handler        = 10
  remediation_engine = 60
}

# Max concurrent Lambda executions (10 is safe for dev to control costs)
lambda_concurrency_limit = 10

# CloudWatch log retention in days
log_retention_days = 7

# Set to true only in a production AWS Organizations management account
cloudtrail_organization_enabled = false

# Point-in-time recovery for DynamoDB (not needed in dev)
enable_pitr = false

# How often Score_Engine rescores all identities
score_engine_schedule = "rate(24 hours)"

# Optional: email addresses to receive SNS security alerts
# email_subscriptions = ["your-email@example.com"]
email_subscriptions = []
https_subscriptions = []

tags = {
  Project     = "Radius"
  Environment = "dev"
  ManagedBy   = "Terraform"
}
