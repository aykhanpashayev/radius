# Production environment configuration for Radius
# Review all values carefully before deploying to production.

environment     = "prod"
aws_region      = "us-east-1"
resource_prefix = "radius"

lambda_s3_bucket = "<REPLACE: your S3 bucket name>"

lambda_memory = {
  event_normalizer   = 512
  detection_engine   = 2048
  incident_processor = 512
  identity_collector = 512
  score_engine       = 2048
  api_handler        = 512
  remediation_engine = 512
}

lambda_timeout = {
  event_normalizer   = 30
  detection_engine   = 120
  incident_processor = 30
  identity_collector = 30
  score_engine       = 120
  api_handler        = 10
  remediation_engine = 60
}

# No concurrency limit in prod (unreserved)
lambda_concurrency_limit = 0

log_retention_days = 365

# Set to true when deploying from an AWS Organizations management account
cloudtrail_organization_enabled = false

enable_pitr = true

score_engine_schedule = "rate(6 hours)"

# Remediation dry-run mode — set to false to enable live IAM remediation actions in prod.
# Ensure remediation rules are reviewed before disabling dry-run.
remediation_dry_run = false

# API Gateway throttling — tighter limits in prod to control costs and protect downstream
api_throttle_burst_limit = 200
api_throttle_rate_limit  = 100

# Required in prod: at least one email for security alerts
email_subscriptions = ["<REPLACE: ops-team@example.com>"]
https_subscriptions = []

tags = {
  Project     = "Radius"
  Environment = "prod"
  ManagedBy   = "Terraform"
}
