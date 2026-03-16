# Function ARNs — used as EventBridge targets and for async invocations
output "function_arns" {
  description = "Map of function name to Lambda function ARN"
  value = {
    event_normalizer   = aws_lambda_function.event_normalizer.arn
    detection_engine   = aws_lambda_function.detection_engine.arn
    incident_processor = aws_lambda_function.incident_processor.arn
    identity_collector = aws_lambda_function.identity_collector.arn
    score_engine       = aws_lambda_function.score_engine.arn
    api_handler        = aws_lambda_function.api_handler.arn
  }
}

# Function names — used in CloudWatch alarms and dashboards
output "function_names" {
  description = "Map of function name to Lambda function name"
  value = {
    event_normalizer   = aws_lambda_function.event_normalizer.function_name
    detection_engine   = aws_lambda_function.detection_engine.function_name
    incident_processor = aws_lambda_function.incident_processor.function_name
    identity_collector = aws_lambda_function.identity_collector.function_name
    score_engine       = aws_lambda_function.score_engine.function_name
    api_handler        = aws_lambda_function.api_handler.function_name
  }
}

# IAM role ARNs — used for auditing and cross-service access
output "role_arns" {
  description = "Map of function name to IAM execution role ARN"
  value = {
    event_normalizer   = aws_iam_role.event_normalizer.arn
    detection_engine   = aws_iam_role.detection_engine.arn
    incident_processor = aws_iam_role.incident_processor.arn
    identity_collector = aws_iam_role.identity_collector.arn
    score_engine       = aws_iam_role.score_engine.arn
    api_handler        = aws_iam_role.api_handler.arn
  }
}

# DLQ ARNs — used in CloudWatch alarms
output "dlq_arns" {
  description = "Map of function name to dead-letter queue ARN (event-driven functions only)"
  value = {
    event_normalizer   = aws_sqs_queue.event_normalizer_dlq.arn
    detection_engine   = aws_sqs_queue.detection_engine_dlq.arn
    incident_processor = aws_sqs_queue.incident_processor_dlq.arn
    identity_collector = aws_sqs_queue.identity_collector_dlq.arn
  }
}
