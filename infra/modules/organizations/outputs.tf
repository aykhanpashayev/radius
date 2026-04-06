output "organization_id" {
  description = "AWS Organizations ID"
  value       = data.aws_organizations_organization.current.id
}

output "organization_root_id" {
  description = "Root ID of the AWS Organization"
  value       = data.aws_organizations_organization.current.roots[0].id
}

output "deny_cloudtrail_policy_id" {
  description = "ID of the DenyDisableCloudTrail SCP"
  value       = aws_organizations_policy.deny_disable_cloudtrail.id
}

output "deny_leave_org_policy_id" {
  description = "ID of the DenyLeaveOrganization SCP"
  value       = aws_organizations_policy.deny_leave_organization.id
}

output "guardduty_detector_id" {
  description = "GuardDuty detector ID in the management account"
  value       = aws_guardduty_detector.management.id
}
