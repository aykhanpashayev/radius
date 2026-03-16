output "dynamodb_key_arn" {
  description = "KMS key ARN for DynamoDB table encryption"
  value       = aws_kms_key.dynamodb.arn
}

output "dynamodb_key_id" {
  description = "KMS key ID for DynamoDB table encryption"
  value       = aws_kms_key.dynamodb.key_id
}

output "lambda_key_arn" {
  description = "KMS key ARN for Lambda environment variable encryption"
  value       = aws_kms_key.lambda.arn
}

output "lambda_key_id" {
  description = "KMS key ID for Lambda environment variable encryption"
  value       = aws_kms_key.lambda.key_id
}

output "sns_key_arn" {
  description = "KMS key ARN for SNS topic encryption"
  value       = aws_kms_key.sns.arn
}

output "sns_key_id" {
  description = "KMS key ID for SNS topic encryption"
  value       = aws_kms_key.sns.key_id
}

output "cloudtrail_key_arn" {
  description = "KMS key ARN for CloudTrail log encryption"
  value       = aws_kms_key.cloudtrail.arn
}

output "cloudtrail_key_id" {
  description = "KMS key ID for CloudTrail log encryption"
  value       = aws_kms_key.cloudtrail.key_id
}
