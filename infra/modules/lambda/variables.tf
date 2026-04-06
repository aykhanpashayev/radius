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
    remediation_engine = number
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
    remediation_engine = number
  })
}

variable "concurrency_limit" {
  description = "Reserved concurrent executions per function. 0 = unreserved (recommended for dev)."
  type        = number
  default     = 0
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

variable "dry_run" {
  description = "When true, Remediation_Engine logs actions without executing them."
  type        = bool
  default     = true
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

variable "vpc_config" {
  description = "VPC configuration for Lambda functions. Set to null to run outside VPC (default). When set, all 7 functions are placed in the specified subnets and security groups."
  type = object({
    subnet_ids         = list(string)
    security_group_ids = list(string)
  })
  default = null
}

variable "secret_arns" {
  description = "List of Secrets Manager secret ARNs that Lambda functions are allowed to read. Grants secretsmanager:GetSecretValue in IAM policies for Incident_Processor and Remediation_Engine."
  type        = list(string)
  default     = []
}
