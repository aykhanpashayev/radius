# API Gateway module for Radius
# REST API with Lambda proxy integration for all 10 operations.

locals {
  common_tags = merge(
    {
      Module      = "apigateway"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# Account-level CloudWatch Logs role for API Gateway
#
# API Gateway requires a single IAM role to be set at the AWS account level
# before it can write access logs to CloudWatch. This is a one-time account
# setting. Without it, any stage with logging enabled fails with:
#   "CloudWatch Logs role ARN must be set in account settings to enable logging"
# ---------------------------------------------------------------------------
resource "aws_iam_role" "api_gateway_cloudwatch" {
  name = "${var.prefix}-apigw-cloudwatch-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "apigateway.amazonaws.com" }
    }]
  })

  tags = local.common_tags
}

resource "aws_iam_role_policy_attachment" "api_gateway_cloudwatch" {
  role       = aws_iam_role.api_gateway_cloudwatch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
}

resource "aws_api_gateway_account" "radius" {
  cloudwatch_role_arn = aws_iam_role.api_gateway_cloudwatch.arn

  depends_on = [aws_iam_role_policy_attachment.api_gateway_cloudwatch]
}

# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------
resource "aws_api_gateway_rest_api" "radius" {
  name        = "${var.prefix}-api"
  description = "Radius cloud security platform REST API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# CloudWatch log group for access logs
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "api_gateway" {
  count             = var.enable_logging ? 1 : 0
  name              = "/aws/apigateway/${var.prefix}-api"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

# ---------------------------------------------------------------------------
# Cognito User Pool authorizer
# All non-OPTIONS methods use this authorizer.
# ---------------------------------------------------------------------------
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${var.prefix}-cognito-authorizer"
  rest_api_id     = aws_api_gateway_rest_api.radius.id
  type            = "COGNITO_USER_POOLS"
  identity_source = "method.request.header.Authorization"
  provider_arns   = [var.cognito_user_pool_arn]
}

# ---------------------------------------------------------------------------
# Gateway responses — ensure CORS headers are present on authorizer
# rejections (401/403) so the browser doesn't show a CORS error instead
# of the actual auth error.
# ---------------------------------------------------------------------------
resource "aws_api_gateway_gateway_response" "unauthorized" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  response_type = "UNAUTHORIZED"
  status_code   = "401"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
  }
}

resource "aws_api_gateway_gateway_response" "access_denied" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  response_type = "ACCESS_DENIED"
  status_code   = "403"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'*'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
  }
}

# ---------------------------------------------------------------------------
# Lambda permission — allow API Gateway to invoke API_Handler
# ---------------------------------------------------------------------------
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.radius.execution_arn}/*/*"
}

# ---------------------------------------------------------------------------
# Deployment and stage (depends on all methods — see endpoints.tf)
# ---------------------------------------------------------------------------
resource "aws_api_gateway_deployment" "radius" {
  rest_api_id = aws_api_gateway_rest_api.radius.id

  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_rest_api.radius.body,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [
    # identities
    aws_api_gateway_integration.get_identities,
    aws_api_gateway_integration.get_identity_by_arn,
    # scores
    aws_api_gateway_integration.get_scores,
    aws_api_gateway_integration.get_score_by_arn,
    # incidents
    aws_api_gateway_integration.get_incidents,
    aws_api_gateway_integration.get_incident_by_id,
    aws_api_gateway_integration.patch_incident_by_id,
    aws_api_gateway_integration.options_incident_by_id,
    # events
    aws_api_gateway_integration.get_events,
    aws_api_gateway_integration.get_event_by_id,
    # trust-relationships
    aws_api_gateway_integration.get_trust_relationships,
    # remediation
    aws_api_gateway_integration.get_remediation_config,
    aws_api_gateway_integration.put_remediation_config_mode,
    aws_api_gateway_integration.options_remediation_config_mode,
    aws_api_gateway_integration.get_remediation_rules,
    aws_api_gateway_integration.post_remediation_rules,
    aws_api_gateway_integration.options_remediation_rules,
    aws_api_gateway_integration.delete_remediation_rule,
    aws_api_gateway_integration.options_remediation_rule_by_id,
    aws_api_gateway_integration.get_remediation_audit,
  ]
}

resource "aws_api_gateway_stage" "radius" {
  deployment_id = aws_api_gateway_deployment.radius.id
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  stage_name    = var.environment

  dynamic "access_log_settings" {
    for_each = var.enable_logging ? [1] : []
    content {
      destination_arn = aws_cloudwatch_log_group.api_gateway[0].arn
      format = jsonencode({
        requestId      = "$context.requestId"
        ip             = "$context.identity.sourceIp"
        caller         = "$context.identity.caller"
        user           = "$context.identity.user"
        requestTime    = "$context.requestTime"
        httpMethod     = "$context.httpMethod"
        resourcePath   = "$context.resourcePath"
        status         = "$context.status"
        protocol       = "$context.protocol"
        responseLength = "$context.responseLength"
      })
    }
  }

  xray_tracing_enabled = false

  # Must wait for the account-level CloudWatch role to be set before
  # enabling logging — otherwise AWS returns a 400 BadRequestException.
  depends_on = [aws_api_gateway_account.radius]

  tags = local.common_tags
}

resource "aws_api_gateway_method_settings" "radius" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  stage_name  = aws_api_gateway_stage.radius.stage_name
  method_path = "*/*"

  settings {
    metrics_enabled    = true
    logging_level      = var.enable_logging ? "INFO" : "OFF"
    data_trace_enabled = false
    throttling_burst_limit = var.throttle_burst_limit
    throttling_rate_limit  = var.throttle_rate_limit
  }
}

# ---------------------------------------------------------------------------
# Usage plan — enforces throttle limits at the stage level
# ---------------------------------------------------------------------------
resource "aws_api_gateway_usage_plan" "radius" {
  name        = "${var.prefix}-usage-plan"
  description = "Throttle limits for the Radius API"

  api_stages {
    api_id = aws_api_gateway_rest_api.radius.id
    stage  = aws_api_gateway_stage.radius.stage_name
  }

  throttle_settings {
    burst_limit = var.throttle_burst_limit
    rate_limit  = var.throttle_rate_limit
  }

  tags = local.common_tags
}
