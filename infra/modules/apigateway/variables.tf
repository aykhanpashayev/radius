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

variable "lambda_function_arn" {
  description = "ARN of the API_Handler Lambda function"
  type        = string
}

variable "lambda_function_name" {
  description = "Name of the API_Handler Lambda function (for permission resource)"
  type        = string
}

variable "cors_allowed_origins" {
  description = "List of allowed CORS origins. Passed into the CORS Allow-Origin response header."
  type        = list(string)
  default     = ["*"]
}

variable "cognito_user_pool_arn" {
  description = "ARN of the Cognito User Pool used to authorize API requests."
  type        = string
}

variable "enable_logging" {
  description = "Enable CloudWatch access logging for API Gateway. Requires the account-level CloudWatch role to be configured (handled automatically by Terraform)."
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Additional tags for API Gateway resources"
  type        = map(string)
  default     = {}
}

variable "throttle_burst_limit" {
  description = "API Gateway throttle burst limit (max concurrent requests)"
  type        = number
  default     = 100
}

variable "throttle_rate_limit" {
  description = "API Gateway throttle rate limit (requests per second)"
  type        = number
  default     = 50
}
