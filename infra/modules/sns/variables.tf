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

variable "kms_key_arn" {
  description = "KMS key ARN for SNS topic encryption"
  type        = string
}

variable "email_subscriptions" {
  description = "List of email addresses to subscribe to the alert topic"
  type        = list(string)
  default     = []
}

variable "https_subscriptions" {
  description = "List of HTTPS webhook URLs to subscribe to the alert topic"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Additional tags for SNS resources"
  type        = map(string)
  default     = {}
}
