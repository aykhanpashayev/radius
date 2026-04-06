variable "prefix" {
  description = "Resource naming prefix (e.g. radius-prod)"
  type        = string
}

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "aws_region" {
  description = "Primary AWS region"
  type        = string
}

variable "kms_key_arn" {
  description = "KMS key ARN used to encrypt the backup vault"
  type        = string
}

variable "table_arns" {
  description = "List of DynamoDB table ARNs to include in the backup plan (PITR-enabled tables only)"
  type        = list(string)
}

variable "backup_retention_days" {
  description = "Number of days to retain backups in the primary vault"
  type        = number
  default     = 35
}

variable "copy_to_region" {
  description = "Secondary region to copy backups to for cross-region DR. Set to empty string to disable."
  type        = string
  default     = ""
}

variable "copy_retention_days" {
  description = "Number of days to retain backup copies in the secondary region vault"
  type        = number
  default     = 30
}

variable "tags" {
  description = "Additional tags for AWS Backup resources"
  type        = map(string)
  default     = {}
}
