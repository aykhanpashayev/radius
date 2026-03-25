variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be either 'dev' or 'prod'."
  }
}

variable "prefix" {
  description = "Resource naming prefix (e.g. radius-dev)"
  type        = string
}

variable "function_configs" {
  description = "Memory allocation (MB) per Lambda function"
  type = object({
    event_normalizer   = number
    detection_engine   = number
    incident_processor = number
    identity_collector = number
    score_engine       = number
    api_handler        = number
  })
}

variable "timeout_configs" {
  description = "Timeout (seconds) per Lambda function"
  type = object({
    event_normalizer   = number
    detection_engine   = number
    incident_processor = number
    identity_collector = number
    score_engine       = number
    api_handler        = number
  })
}

variable "concurrency_limit" {
  description = "Reserved concurrent executions per function (null = unreserved)"
  type        = number
  default     = null
}

variable "dynamodb_table_names" {
  description = "Map of DynamoDB table names injected as Lambda environment variables"
  type = object({
    identity_profile      = string
    blast_radius_score    = string
    incident              = string
    event_summary         = string
    trust_relationship    = string
    remediation_config    = string
    remediation_audit_log = string
  })
}

variable "dynamodb_table_arns" {
  description = "Map of DynamoDB table ARNs used in IAM policies"
  type = object({
    identity_profile      = string
    blast_radius_score    = string
    incident              = string
    event_summary         = string
    trust_relationship    = string
    remediation_config    = string
    remediation_audit_log = string
  })
}

variable "dynamodb_gsi_arns" {
  description = "Map of DynamoDB GSI ARNs used in IAM policies"
  type        = map(list(string))
}

variable "sns_topic_arn" {
  description = "SNS Alert_Topic ARN for Incident_Processor"
  type        = string
}

variable "remediation_topic_arn" {
  description = "SNS Remediation_Topic ARN for Remediation_Engine"
  type        = string
  default     = ""
}

variable "kms_key_arn" {
  description = "KMS key ARN for Lambda environment variable encryption"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 7
}

variable "lambda_s3_bucket" {
  description = "S3 bucket containing Lambda deployment packages"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
}

variable "tags" {
  description = "Additional tags for Lambda resources"
  type        = map(string)
  default     = {}
}
