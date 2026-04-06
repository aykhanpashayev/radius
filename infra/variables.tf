variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

variable "resource_prefix" {
  description = "Prefix for all resource names"
  type        = string
  default     = "radius"
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-east-1"
}

variable "lambda_memory" {
  description = "Memory allocation for Lambda functions (MB)"
  type = object({
    event_normalizer   = number
    detection_engine   = number
    incident_processor = number
    identity_collector = number
    score_engine       = number
    api_handler        = number
    remediation_engine = number
  })
  default = {
    event_normalizer   = 512
    detection_engine   = 1024
    incident_processor = 512
    identity_collector = 512
    score_engine       = 1024
    api_handler        = 256
    remediation_engine = 256
  }
}

variable "lambda_timeout" {
  description = "Timeout for Lambda functions (seconds)"
  type = object({
    event_normalizer   = number
    detection_engine   = number
    incident_processor = number
    identity_collector = number
    score_engine       = number
    api_handler        = number
    remediation_engine = number
  })
  default = {
    event_normalizer   = 30
    detection_engine   = 60
    incident_processor = 30
    identity_collector = 30
    score_engine       = 60
    api_handler        = 10
    remediation_engine = 60
  }
}

variable "lambda_concurrency_limit" {
  description = "Reserved concurrent executions for Lambda functions"
  type        = number
  default     = 10
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 7
}

variable "cloudtrail_organization_enabled" {
  description = "Enable organization-wide CloudTrail (prod only)"
  type        = bool
  default     = false
}

variable "enable_pitr" {
  description = "Enable point-in-time recovery for DynamoDB tables"
  type        = bool
  default     = true
}

variable "lambda_s3_bucket" {
  description = "S3 bucket name containing Lambda deployment packages"
  type        = string
  default     = ""
}

variable "email_subscriptions" {
  description = "Email addresses to subscribe to the SNS alert topic"
  type        = list(string)
  default     = []
}

variable "https_subscriptions" {
  description = "HTTPS webhook URLs to subscribe to the SNS alert topic"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default     = {}
}

variable "score_engine_schedule" {
  description = "EventBridge schedule expression for batch scoring (e.g. rate(6 hours))"
  type        = string
  default     = "rate(24 hours)"
}

variable "remediation_dry_run" {
  description = "When true, Remediation_Engine logs actions without executing them. Defaults to true — must be explicitly set to false in prod to enable live remediation."
  type        = bool
  default     = true
}

variable "api_throttle_burst_limit" {
  description = "API Gateway throttle burst limit (max concurrent requests)"
  type        = number
  default     = 100
}

variable "api_throttle_rate_limit" {
  description = "API Gateway throttle rate limit (requests per second)"
  type        = number
  default     = 50
}

variable "log_level" {
  description = "Log level for all Lambda functions (DEBUG, INFO, WARNING, ERROR)"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["DEBUG", "INFO", "WARNING", "ERROR"], var.log_level)
    error_message = "log_level must be one of: DEBUG, INFO, WARNING, ERROR."
  }
}

variable "cognito_callback_urls" {
  description = "Override Cognito OAuth callback URLs. Defaults to the CloudFront distribution URL."
  type        = list(string)
  default     = []
}

variable "cognito_logout_urls" {
  description = "Override Cognito OAuth logout URLs. Defaults to the CloudFront distribution URL."
  type        = list(string)
  default     = []
}

variable "github_repo" {
  description = "GitHub repository in org/repo format for the OIDC deploy role (e.g. my-org/radius). Leave empty to skip OIDC role creation."
  type        = string
  default     = ""
}

variable "enable_waf" {
  description = "Attach a WAF v2 Web ACL to the API Gateway stage (recommended for prod)"
  type        = bool
  default     = false
}

variable "waf_rate_limit" {
  description = "Maximum requests per 5-minute window per source IP before WAF blocks the request"
  type        = number
  default     = 300
}

variable "enable_vpc" {
  description = "Place Lambda functions inside a VPC with private subnets and VPC endpoints (recommended for prod)"
  type        = bool
  default     = false
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC when enable_vpc = true"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "AZs to deploy VPC private subnets into (minimum 2)"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "enable_secrets_manager" {
  description = "Provision Secrets Manager secrets for alerting webhook integrations (PagerDuty, OpsGenie)"
  type        = bool
  default     = false
}
