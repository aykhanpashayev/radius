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

# Module outputs will be added as modules are implemented
# Example structure:
# output "dynamodb_table_names" {
#   description = "DynamoDB table names"
#   value       = module.dynamodb.table_names
# }
#
# output "lambda_function_arns" {
#   description = "Lambda function ARNs"
#   value       = module.lambda.function_arns
# }
#
# output "api_endpoint" {
#   description = "API Gateway endpoint URL"
#   value       = module.apigateway.api_endpoint
# }
