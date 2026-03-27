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

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "lambda_function_names" {
  description = "Map of Lambda function names for alarm and dashboard configuration"
  type = object({
    event_normalizer   = string
    detection_engine   = string
    incident_processor = string
    identity_collector = string
    score_engine       = string
    api_handler        = string
  })
}

variable "dynamodb_table_names" {
  description = "Map of DynamoDB table names for alarm configuration"
  type = object({
    identity_profile   = string
    blast_radius_score = string
    incident           = string
    event_summary      = string
    trust_relationship = string
  })
}

variable "api_gateway_name" {
  description = "API Gateway name for dashboard metrics"
  type        = string
}

variable "dlq_arns" {
  description = "Map of dead-letter queue names for alarm configuration"
  type        = map(string)
  default     = {}
}

variable "alarm_sns_topic_arn" {
  description = "SNS topic ARN for CloudWatch alarm notifications"
  type        = string
}

variable "aws_region" {
  description = "AWS region for dashboard metric widgets"
  type        = string
  default     = "us-east-1"
}

variable "tags" {
  description = "Additional tags for CloudWatch resources"
  type        = map(string)
  default     = {}
}
