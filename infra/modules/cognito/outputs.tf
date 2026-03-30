output "user_pool_id" {
  description = "Cognito User Pool ID"
  value       = aws_cognito_user_pool.radius.id
}

output "user_pool_arn" {
  description = "Cognito User Pool ARN"
  value       = aws_cognito_user_pool.radius.arn
}

output "client_id" {
  description = "Cognito User Pool Client ID (for frontend config)"
  value       = aws_cognito_user_pool_client.dashboard.id
}

output "domain" {
  description = "Cognito hosted UI domain prefix"
  value       = aws_cognito_user_pool_domain.radius.domain
}
