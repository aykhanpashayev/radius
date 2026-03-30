output "environment" {
  description = "Deployment environment"
  value       = var.environment
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "resource_prefix" {
  description = "Resource naming prefix"
  value       = var.resource_prefix
}

output "api_endpoint" {
  description = "API Gateway invoke URL"
  value       = module.apigateway.api_endpoint
}

output "dynamodb_table_names" {
  description = "DynamoDB table names"
  value       = module.dynamodb.table_names
}

output "lambda_function_arns" {
  description = "Lambda function ARNs"
  value       = module.lambda.function_arns
}

output "lambda_function_names" {
  description = "Lambda function names"
  value       = module.lambda.function_names
}

output "sns_alert_topic_arn" {
  description = "SNS Alert_Topic ARN"
  value       = module.sns.alert_topic_arn
}

output "sns_remediation_topic_arn" {
  description = "SNS Remediation_Topic ARN"
  value       = module.sns.remediation_topic_arn
}

output "cloudtrail_trail_arn" {
  description = "CloudTrail trail ARN"
  value       = module.cloudtrail.trail_arn
}

output "cloudtrail_s3_bucket" {
  description = "S3 bucket name for CloudTrail logs"
  value       = module.cloudtrail.s3_bucket_name
}

output "cloudwatch_dashboard_names" {
  description = "CloudWatch dashboard names"
  value       = module.cloudwatch.dashboard_names
}

output "kms_key_arns" {
  description = "KMS key ARNs by service"
  value = {
    dynamodb   = module.kms.dynamodb_key_arn
    lambda     = module.kms.lambda_key_arn
    sns        = module.kms.sns_key_arn
    cloudtrail = module.kms.cloudtrail_key_arn
  }
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID"
  value       = module.cognito.user_pool_id
}

output "cognito_client_id" {
  description = "Cognito User Pool Client ID (set as VITE_COGNITO_CLIENT_ID in frontend/.env)"
  value       = module.cognito.client_id
}

output "cognito_domain" {
  description = "Cognito hosted UI domain prefix"
  value       = module.cognito.domain
}
