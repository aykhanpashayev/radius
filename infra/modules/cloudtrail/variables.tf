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
  description = "KMS key ARN for CloudTrail log encryption"
  type        = string
}

variable "organization_enabled" {
  description = "Enable organization-wide trail (prod) vs single-account trail (dev)"
  type        = bool
  default     = false
}

variable "log_retention_days" {
  description = "S3 lifecycle transition to Glacier after this many days"
  type        = number
  default     = 90
}

variable "log_expiration_days" {
  description = "S3 lifecycle deletion after this many days"
  type        = number
  default     = 365
}

variable "tags" {
  description = "Additional tags for CloudTrail resources"
  type        = map(string)
  default     = {}
}
