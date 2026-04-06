output "bucket_name" {
  description = "S3 bucket name for frontend assets"
  value       = aws_s3_bucket.frontend.id
}

output "bucket_arn" {
  description = "S3 bucket ARN"
  value       = aws_s3_bucket.frontend.arn
}

output "distribution_id" {
  description = "CloudFront distribution ID (used for cache invalidation)"
  value       = aws_cloudfront_distribution.frontend.id
}

output "domain_name" {
  description = "CloudFront distribution domain name (e.g. d1234.cloudfront.net)"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "url" {
  description = "Full HTTPS URL of the deployed dashboard"
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
}
