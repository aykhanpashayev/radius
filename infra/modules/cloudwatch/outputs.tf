output "dashboard_names" {
  description = "Map of CloudWatch dashboard names"
  value = {
    lambda      = aws_cloudwatch_dashboard.lambda.dashboard_name
    dynamodb    = aws_cloudwatch_dashboard.dynamodb.dashboard_name
    api_gateway = aws_cloudwatch_dashboard.api_gateway.dashboard_name
    eventbridge = aws_cloudwatch_dashboard.eventbridge.dashboard_name
  }
}

output "alarm_arns" {
  description = "Map of CloudWatch alarm ARNs by function name"
  value = {
    lambda_error_rate = { for k, v in aws_cloudwatch_metric_alarm.lambda_error_rate : k => v.arn }
    dynamodb_throttles = { for k, v in aws_cloudwatch_metric_alarm.dynamodb_throttles : k => v.arn }
    api_gateway_5xx   = aws_cloudwatch_metric_alarm.api_gateway_5xx.arn
  }
}
