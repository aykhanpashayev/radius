variable "prefix" {
  description = "Resource naming prefix (e.g. radius-prod)"
  type        = string
}

variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "api_stage_arn" {
  description = "ARN of the API Gateway stage to associate the WAF ACL with"
  type        = string
}

variable "rate_limit" {
  description = "Max requests per 5-minute window per source IP before blocking"
  type        = number
  default     = 300
}

variable "tags" {
  description = "Additional tags for WAF resources"
  type        = map(string)
  default     = {}
}
