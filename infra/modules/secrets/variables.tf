variable "prefix" {
  description = "Resource naming prefix (e.g. radius-prod)"
  type        = string
}

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN for Secrets Manager encryption. If empty, uses the AWS-managed key."
  type        = string
  default     = ""
}

variable "tags" {
  description = "Additional tags for Secrets Manager resources"
  type        = map(string)
  default     = {}
}
