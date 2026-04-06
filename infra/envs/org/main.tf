# AWS Organizations bootstrap entry point.
# Deploy ONCE from the Organizations management account, before or alongside
# the prod application deploy. Uses a separate S3 state key from dev/prod.
#
# Prerequisites:
#   - AWS credentials must belong to the Organizations management account
#   - SCP feature must be enabled: aws organizations enable-policy-type \
#       --root-id <root-id> --policy-type SERVICE_CONTROL_POLICY
#   - GuardDuty must not already have a delegated admin configured
#
# Usage:
#   terraform init -backend-config=backend.tfvars
#   terraform apply -var-file=terraform.tfvars

terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    # Values supplied via backend.tfvars at init time
  }
}

provider "aws" {
  region = var.aws_region
}

module "organizations" {
  source = "../../modules/organizations"

  security_account_id      = var.security_account_id
  cloudtrail_s3_bucket_arn = var.cloudtrail_s3_bucket_arn
  tags                     = var.tags
}

# ---------------------------------------------------------------------------
# Pass-through variables
# ---------------------------------------------------------------------------
variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "security_account_id" {
  description = "AWS account ID where Radius is deployed"
  type        = string
}

variable "cloudtrail_s3_bucket_arn" {
  description = "ARN of the Radius prod CloudTrail S3 bucket (from prod terraform output)"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
output "organization_id" { value = module.organizations.organization_id }
output "organization_root_id" { value = module.organizations.organization_root_id }
output "deny_cloudtrail_policy_id" { value = module.organizations.deny_cloudtrail_policy_id }
output "deny_leave_org_policy_id" { value = module.organizations.deny_leave_org_policy_id }
output "guardduty_detector_id" { value = module.organizations.guardduty_detector_id }
