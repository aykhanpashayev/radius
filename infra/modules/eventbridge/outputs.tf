output "rule_arns" {
  description = "List of EventBridge rule ARNs"
  value       = [aws_cloudwatch_event_rule.cloudtrail_management.arn]
}

output "rule_name" {
  description = "Name of the CloudTrail management events rule"
  value       = aws_cloudwatch_event_rule.cloudtrail_management.name
}

output "event_bus_arn" {
  description = "Default event bus ARN"
  value       = "arn:aws:events:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:event-bus/default"
}

output "dlq_arn" {
  description = "Dead-letter queue ARN for failed EventBridge deliveries"
  value       = aws_sqs_queue.eventbridge_dlq.arn
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
