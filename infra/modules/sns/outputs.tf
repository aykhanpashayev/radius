output "alert_topic_arn" {
  description = "ARN of the Alert_Topic SNS topic"
  value       = aws_sns_topic.alert_topic.arn
}

output "alert_topic_name" {
  description = "Name of the Alert_Topic SNS topic"
  value       = aws_sns_topic.alert_topic.name
}

output "remediation_topic_arn" {
  description = "ARN of the Remediation_Topic SNS topic"
  value       = aws_sns_topic.remediation_topic.arn
}

output "remediation_topic_name" {
  description = "Name of the Remediation_Topic SNS topic"
  value       = aws_sns_topic.remediation_topic.name
}
