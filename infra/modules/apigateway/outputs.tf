output "api_endpoint" {
  description = "API Gateway invoke URL"
  value       = aws_api_gateway_stage.radius.invoke_url
}

output "api_id" {
  description = "API Gateway REST API ID"
  value       = aws_api_gateway_rest_api.radius.id
}

output "api_arn" {
  description = "API Gateway REST API ARN"
  value       = aws_api_gateway_rest_api.radius.arn
}

output "execution_arn" {
  description = "API Gateway execution ARN (used for Lambda permissions)"
  value       = aws_api_gateway_rest_api.radius.execution_arn
}

output "stage_name" {
  description = "Deployed stage name"
  value       = aws_api_gateway_stage.radius.stage_name
}
