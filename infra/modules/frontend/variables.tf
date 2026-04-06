variable "environment" {
  description = "Environment name (dev or prod)"
  type        = string
}

variable "prefix" {
  description = "Resource naming prefix (e.g. radius-dev)"
  type        = string
}

variable "tags" {
  description = "Tags to apply to all frontend resources"
  type        = map(string)
  default     = {}
}
