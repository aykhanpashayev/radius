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

variable "lambda_function_arns" {
  description = "Map of Lambda function ARNs for EventBridge targets"
  type = object({
    event_normalizer = string
  })
}

variable "event_filters" {
  description = "List of additional event source filters (merged with default IAM/STS/Orgs/EC2 filter)"
  type        = list(string)
  default     = []
}

variable "score_engine_schedule" {
  description = "EventBridge schedule expression for batch scoring (e.g. rate(6 hours))"
  type        = string
}

variable "score_engine_function_arn" {
  description = "ARN of the Score_Engine Lambda function for batch scheduling"
  type        = string
}

variable "tags" {
  description = "Additional tags for EventBridge resources"
  type        = map(string)
  default     = {}
}
