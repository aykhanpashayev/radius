output "trail_arn" {
  description = "CloudTrail trail ARN"
  value       = aws_cloudtrail.radius.arn
}

output "trail_name" {
  description = "CloudTrail trail name"
  value       = aws_cloudtrail.radius.name
}

output "s3_bucket_name" {
  description = "S3 bucket name for CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail_logs.id
}

output "s3_bucket_arn" {
  description = "S3 bucket ARN for CloudTrail logs"
  value       = aws_s3_bucket.cloudtrail_logs.arn
}
