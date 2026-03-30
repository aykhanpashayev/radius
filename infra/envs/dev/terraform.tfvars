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

# Max concurrent Lambda executions per function.
# Set to 0 to use unreserved concurrency (recommended for dev).
# If you set this to a number, it reserves that many executions PER function.
# With 7 functions at concurrency=10, that's 70 reserved total — your account
# needs at least 80 total concurrent executions available (70 reserved + 10 unreserved minimum).
# Most accounts default to 1000, so this is fine. Set to 0 if you hit concurrency errors.
lambda_concurrency_limit = 0

# CloudWatch log retention in days
log_retention_days = 7

# Set to true only in a production AWS Organizations management account
cloudtrail_organization_enabled = false

# Point-in-time recovery for DynamoDB — enabled by default, disable only to cut costs in throwaway envs
enable_pitr = true

# How often Score_Engine rescores all identities
score_engine_schedule = "rate(24 hours)"

# Remediation dry-run mode — true means actions are logged but not executed.
# Safe default for dev. Set to false in prod only when you're ready for live remediation.
remediation_dry_run = true

# API Gateway throttling — limits per-stage to protect Lambda and DynamoDB from floods
api_throttle_burst_limit = 50
api_throttle_rate_limit  = 25

# Optional: email addresses to receive SNS security alerts
# email_subscriptions = ["your-email@example.com"]
email_subscriptions = []
https_subscriptions = []

tags = {
  Project     = "Radius"
  Environment = "dev"
  ManagedBy   = "Terraform"
}
