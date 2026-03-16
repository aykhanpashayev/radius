output "alert_topic_arn" {
  description = "ARN of the Alert_Topic SNS topic"
  value       = aws_sns_topic.alert_topic.arn
}

output "alert_topic_name" {
  description = "Name of the Alert_Topic SNS topic"
  value       = aws_sns_topic.alert_topic.name
}
