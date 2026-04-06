output "backup_vault_arn" {
  description = "ARN of the AWS Backup vault"
  value       = aws_backup_vault.radius.arn
}

output "backup_vault_name" {
  description = "Name of the AWS Backup vault"
  value       = aws_backup_vault.radius.name
}

output "backup_plan_id" {
  description = "ID of the AWS Backup plan"
  value       = aws_backup_plan.radius.id
}

output "backup_role_arn" {
  description = "IAM role ARN used by AWS Backup"
  value       = aws_iam_role.backup.arn
}
