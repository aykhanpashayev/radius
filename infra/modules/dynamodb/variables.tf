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

variable "billing_mode" {
  description = "DynamoDB billing mode"
  type        = string
  default     = "PAY_PER_REQUEST"
  validation {
    condition     = contains(["PAY_PER_REQUEST", "PROVISIONED"], var.billing_mode)
    error_message = "Billing mode must be PAY_PER_REQUEST or PROVISIONED."
  }
}

variable "enable_pitr" {
  description = "Enable point-in-time recovery for critical tables (Identity_Profile, Blast_Radius_Score, Incident)"
  type        = bool
  default     = false
}

variable "kms_key_arn" {
  description = "KMS key ARN for DynamoDB encryption at rest"
  type        = string
}

variable "event_summary_ttl_days" {
  description = "TTL in days for Event_Summary records"
  type        = number
  default     = 90
}

variable "incident_ttl_days" {
  description = "TTL in days for resolved Incident records"
  type        = number
  default     = 90
}

variable "tags" {
  description = "Additional tags for DynamoDB resources"
  type        = map(string)
  default     = {}
}
