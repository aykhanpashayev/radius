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
    # events
    aws_api_gateway_integration.get_events,
    aws_api_gateway_integration.get_event_by_id,
    # trust-relationships
    aws_api_gateway_integration.get_trust_relationships,
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
  }
}
