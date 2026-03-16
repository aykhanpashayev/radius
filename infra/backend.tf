# Backend configuration for Terraform state
# This file defines the S3 backend with DynamoDB locking
# Actual backend configuration values are provided via backend.tfvars files in envs/

terraform {
  backend "s3" {
    # Backend configuration is provided via -backend-config flag during terraform init
    # See infra/envs/dev/backend.tfvars and infra/envs/prod/backend.tfvars

    # Required values (provided via backend.tfvars):
    # - bucket: S3 bucket name for state storage
    # - key: Path to state file within bucket
    # - region: AWS region for state bucket
    # - dynamodb_table: DynamoDB table for state locking
    # - encrypt: Enable encryption at rest (true)
    # - kms_key_id: KMS key ARN for encryption (optional)
  }
}
