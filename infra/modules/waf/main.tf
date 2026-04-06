# WAF v2 Web ACL for the Radius REST API.
# Scope is REGIONAL (API Gateway uses regional scope, not CLOUDFRONT).
# Association links the ACL to the API Gateway stage ARN.
#
# Managed rule groups start in COUNT mode — this lets you observe which
# requests would be blocked in CloudWatch before switching to BLOCK.
# Once you've validated no false positives, change override_action to
# none {} (which enforces the managed rules' own actions).

locals {
  common_tags = merge(
    {
      Module      = "waf"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# CloudWatch log group for WAF sampled requests
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "waf" {
  # WAF log group names must start with "aws-waf-logs-"
  name              = "aws-waf-logs-${var.prefix}-api"
  retention_in_days = 90
  tags              = local.common_tags
}

# ---------------------------------------------------------------------------
# Web ACL
# ---------------------------------------------------------------------------
resource "aws_wafv2_web_acl" "radius" {
  name        = "${var.prefix}-api-waf"
  description = "WAF protection for the Radius REST API"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  # ---------------------------------------------------------------------------
  # Rule 1 — IP-based rate limiting (evaluated first, lowest priority number)
  # Blocks any single IP that exceeds var.rate_limit requests per 5 minutes.
  # ---------------------------------------------------------------------------
  rule {
    name     = "rate-limit-per-ip"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = var.rate_limit
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.prefix}-waf-rate-limit"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 2 — AWS Common Rule Set (OWASP Top 10 protections)
  # override_action = count  →  observe only (change to none {} to enforce)
  # ---------------------------------------------------------------------------
  rule {
    name     = "aws-managed-common-rules"
    priority = 10

    override_action {
      count {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.prefix}-waf-common-rules"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 3 — Known Bad Inputs (Log4j, SQL injection patterns, etc.)
  # ---------------------------------------------------------------------------
  rule {
    name     = "aws-managed-bad-inputs"
    priority = 20

    override_action {
      count {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.prefix}-waf-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  # ---------------------------------------------------------------------------
  # Rule 4 — Amazon IP Reputation List (known botnets, scanners, tor exits)
  # ---------------------------------------------------------------------------
  rule {
    name     = "aws-managed-ip-reputation"
    priority = 30

    override_action {
      count {}
    }

    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesAmazonIpReputationList"
        vendor_name = "AWS"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "${var.prefix}-waf-ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${var.prefix}-waf-acl"
    sampled_requests_enabled   = true
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# Associate WAF ACL with the API Gateway stage
# ---------------------------------------------------------------------------
resource "aws_wafv2_web_acl_association" "radius" {
  resource_arn = var.api_stage_arn
  web_acl_arn  = aws_wafv2_web_acl.radius.arn
}

# ---------------------------------------------------------------------------
# Enable WAF logging to CloudWatch
# ---------------------------------------------------------------------------
resource "aws_wafv2_web_acl_logging_configuration" "radius" {
  log_destination_configs = [aws_cloudwatch_log_group.waf.arn]
  resource_arn            = aws_wafv2_web_acl.radius.arn
}
