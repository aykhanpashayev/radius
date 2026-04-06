output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.radius.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets where Lambda functions are placed"
  value       = aws_subnet.private[*].id
}

output "lambda_security_group_id" {
  description = "ID of the security group attached to Lambda functions"
  value       = aws_security_group.lambda.id
}

output "vpc_config" {
  description = "Structured vpc_config object ready to pass directly to the lambda module"
  value = {
    subnet_ids         = aws_subnet.private[*].id
    security_group_ids = [aws_security_group.lambda.id]
  }
}
