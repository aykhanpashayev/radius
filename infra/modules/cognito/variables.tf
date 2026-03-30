variable "prefix" {
  description = "Resource naming prefix (e.g. radius-dev)"
  type        = string
}

variable "callback_urls" {
  description = "Allowed OAuth callback URLs (e.g. CloudFront domain + /callback)"
  type        = list(string)
}

variable "logout_urls" {
  description = "Allowed OAuth logout URLs"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to all Cognito resources"
  type        = map(string)
  default     = {}
}
