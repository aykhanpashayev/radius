output "pagerduty_secret_arn" {
  description = "ARN of the PagerDuty integration key secret"
  value       = aws_secretsmanager_secret.pagerduty.arn
}

output "opsgenie_secret_arn" {
  description = "ARN of the OpsGenie API key secret"
  value       = aws_secretsmanager_secret.opsgenie.arn
}

output "secret_arns" {
  description = "List of all secret ARNs — passed to Lambda IAM policies to grant GetSecretValue"
  value = [
    aws_secretsmanager_secret.pagerduty.arn,
    aws_secretsmanager_secret.opsgenie.arn,
  ]
}
