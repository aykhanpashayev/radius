# Terraform remote state configuration for the dev environment.
# These values tell Terraform where to store its state file in S3.
#
# Before running terraform init, create the S3 bucket and DynamoDB lock table:
#
#   aws s3 mb s3://<your-state-bucket> --region us-east-1
#   aws s3api put-bucket-versioning \
#     --bucket <your-state-bucket> \
#     --versioning-configuration Status=Enabled
#
# The DynamoDB lock table is created automatically by Terraform on first init.

bucket         = "<REPLACE: your Terraform state S3 bucket name>"
key            = "radius/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "radius-terraform-locks"
encrypt        = true
