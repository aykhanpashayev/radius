variable "security_account_id" {
  description = "AWS account ID where Radius is deployed (receives delegated admin permissions)"
  type        = string
}

variable "cloudtrail_s3_bucket_arn" {
  description = "ARN of the S3 bucket that the org-wide CloudTrail writes logs to"
  type        = string
}

variable "tags" {
  description = "Additional tags for Organizations resources"
  type        = map(string)
  default     = {}
}
