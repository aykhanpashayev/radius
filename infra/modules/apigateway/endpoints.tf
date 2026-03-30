# API Gateway endpoint definitions for Radius.
# All non-GET methods require an OPTIONS mock integration for CORS preflight.
# The OPTIONS response returns Access-Control-Allow-* headers directly from
# API Gateway without invoking Lambda — this is the standard pattern.

locals {
  lambda_uri = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"

  # Use the first entry from cors_allowed_origins. For multi-origin support,
  # the Lambda handler should echo back the request Origin if it matches the list.
  cors_origin = length(var.cors_allowed_origins) == 1 ? "'${var.cors_allowed_origins[0]}'" : "'${var.cors_allowed_origins[0]}'"

  cors_response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = local.cors_origin
  }

  cors_response_templates = {
    "application/json" = ""
  }

  # Authorizer ID — empty string when no Cognito pool is configured (dev/local).
  authorizer_id = var.cognito_user_pool_arn != "" ? aws_api_gateway_authorizer.cognito[0].id : null
  authorization = var.cognito_user_pool_arn != "" ? "COGNITO_USER_POOLS" : "NONE"
}

data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# Helper: reusable OPTIONS mock integration for CORS preflight
# Every resource that has PATCH/POST/PUT/DELETE needs one of these.
# ---------------------------------------------------------------------------

# ===========================================================================
# /identities
# ===========================================================================
resource "aws_api_gateway_resource" "identities" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_rest_api.radius.root_resource_id
  path_part   = "identities"
}

resource "aws_api_gateway_method" "get_identities" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.identities.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_identities" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.identities.id
  http_method             = aws_api_gateway_method.get_identities.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# /identities/{arn}
resource "aws_api_gateway_resource" "identity_by_arn" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.identities.id
  path_part   = "{arn}"
}

resource "aws_api_gateway_method" "get_identity_by_arn" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.identity_by_arn.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
  request_parameters = { "method.request.path.arn" = true }
}

resource "aws_api_gateway_integration" "get_identity_by_arn" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.identity_by_arn.id
  http_method             = aws_api_gateway_method.get_identity_by_arn.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# ===========================================================================
# /scores
# ===========================================================================
resource "aws_api_gateway_resource" "scores" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_rest_api.radius.root_resource_id
  path_part   = "scores"
}

resource "aws_api_gateway_method" "get_scores" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.scores.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_scores" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.scores.id
  http_method             = aws_api_gateway_method.get_scores.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# /scores/{arn}
resource "aws_api_gateway_resource" "score_by_arn" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.scores.id
  path_part   = "{arn}"
}

resource "aws_api_gateway_method" "get_score_by_arn" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.score_by_arn.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
  request_parameters = { "method.request.path.arn" = true }
}

resource "aws_api_gateway_integration" "get_score_by_arn" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.score_by_arn.id
  http_method             = aws_api_gateway_method.get_score_by_arn.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# ===========================================================================
# /incidents
# ===========================================================================
resource "aws_api_gateway_resource" "incidents" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_rest_api.radius.root_resource_id
  path_part   = "incidents"
}

resource "aws_api_gateway_method" "get_incidents" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.incidents.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_incidents" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.incidents.id
  http_method             = aws_api_gateway_method.get_incidents.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# /incidents/{id}
resource "aws_api_gateway_resource" "incident_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.incidents.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "get_incident_by_id" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.incident_by_id.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
  request_parameters = { "method.request.path.id" = true }
}

resource "aws_api_gateway_integration" "get_incident_by_id" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.incident_by_id.id
  http_method             = aws_api_gateway_method.get_incident_by_id.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

resource "aws_api_gateway_method" "patch_incident_by_id" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.incident_by_id.id
  http_method   = "PATCH"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
  request_parameters = { "method.request.path.id" = true }
}

resource "aws_api_gateway_integration" "patch_incident_by_id" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.incident_by_id.id
  http_method             = aws_api_gateway_method.patch_incident_by_id.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# OPTIONS /incidents/{id} — required for CORS preflight on PATCH
resource "aws_api_gateway_method" "options_incident_by_id" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.incident_by_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_incident_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.incident_by_id.id
  http_method = aws_api_gateway_method.options_incident_by_id.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_incident_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.incident_by_id.id
  http_method = aws_api_gateway_method.options_incident_by_id.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_incident_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.incident_by_id.id
  http_method = aws_api_gateway_method.options_incident_by_id.http_method
  status_code = aws_api_gateway_method_response.options_incident_by_id.status_code
  response_parameters = local.cors_response_parameters
  response_templates  = local.cors_response_templates
  depends_on          = [aws_api_gateway_integration.options_incident_by_id]
}

# ===========================================================================
# /events
# ===========================================================================
resource "aws_api_gateway_resource" "events" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_rest_api.radius.root_resource_id
  path_part   = "events"
}

resource "aws_api_gateway_method" "get_events" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.events.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_events" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.events.id
  http_method             = aws_api_gateway_method.get_events.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# /events/{id}
resource "aws_api_gateway_resource" "event_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.events.id
  path_part   = "{id}"
}

resource "aws_api_gateway_method" "get_event_by_id" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.event_by_id.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
  request_parameters = { "method.request.path.id" = true }
}

resource "aws_api_gateway_integration" "get_event_by_id" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.event_by_id.id
  http_method             = aws_api_gateway_method.get_event_by_id.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# ===========================================================================
# /trust-relationships
# ===========================================================================
resource "aws_api_gateway_resource" "trust_relationships" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_rest_api.radius.root_resource_id
  path_part   = "trust-relationships"
}

resource "aws_api_gateway_method" "get_trust_relationships" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.trust_relationships.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_trust_relationships" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.trust_relationships.id
  http_method             = aws_api_gateway_method.get_trust_relationships.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# ===========================================================================
# /remediation/config
# ===========================================================================
resource "aws_api_gateway_resource" "remediation" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_rest_api.radius.root_resource_id
  path_part   = "remediation"
}

resource "aws_api_gateway_resource" "remediation_config" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.remediation.id
  path_part   = "config"
}

resource "aws_api_gateway_method" "get_remediation_config" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_config.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_remediation_config" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.remediation_config.id
  http_method             = aws_api_gateway_method.get_remediation_config.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# /remediation/config/mode
resource "aws_api_gateway_resource" "remediation_config_mode" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.remediation_config.id
  path_part   = "mode"
}

resource "aws_api_gateway_method" "put_remediation_config_mode" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_config_mode.id
  http_method   = "PUT"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "put_remediation_config_mode" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.remediation_config_mode.id
  http_method             = aws_api_gateway_method.put_remediation_config_mode.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# OPTIONS /remediation/config/mode
resource "aws_api_gateway_method" "options_remediation_config_mode" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_config_mode.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_remediation_config_mode" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_config_mode.id
  http_method = aws_api_gateway_method.options_remediation_config_mode.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_remediation_config_mode" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_config_mode.id
  http_method = aws_api_gateway_method.options_remediation_config_mode.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_remediation_config_mode" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_config_mode.id
  http_method = aws_api_gateway_method.options_remediation_config_mode.http_method
  status_code = aws_api_gateway_method_response.options_remediation_config_mode.status_code
  response_parameters = local.cors_response_parameters
  response_templates  = local.cors_response_templates
  depends_on          = [aws_api_gateway_integration.options_remediation_config_mode]
}

# ===========================================================================
# /remediation/rules
# ===========================================================================
resource "aws_api_gateway_resource" "remediation_rules" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.remediation.id
  path_part   = "rules"
}

resource "aws_api_gateway_method" "get_remediation_rules" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_rules.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_remediation_rules" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.remediation_rules.id
  http_method             = aws_api_gateway_method.get_remediation_rules.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

resource "aws_api_gateway_method" "post_remediation_rules" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_rules.id
  http_method   = "POST"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "post_remediation_rules" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.remediation_rules.id
  http_method             = aws_api_gateway_method.post_remediation_rules.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# OPTIONS /remediation/rules
resource "aws_api_gateway_method" "options_remediation_rules" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_rules.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_remediation_rules" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_rules.id
  http_method = aws_api_gateway_method.options_remediation_rules.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_remediation_rules" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_rules.id
  http_method = aws_api_gateway_method.options_remediation_rules.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_remediation_rules" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_rules.id
  http_method = aws_api_gateway_method.options_remediation_rules.http_method
  status_code = aws_api_gateway_method_response.options_remediation_rules.status_code
  response_parameters = local.cors_response_parameters
  response_templates  = local.cors_response_templates
  depends_on          = [aws_api_gateway_integration.options_remediation_rules]
}

# /remediation/rules/{rule_id}
resource "aws_api_gateway_resource" "remediation_rule_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.remediation_rules.id
  path_part   = "{rule_id}"
}

resource "aws_api_gateway_method" "delete_remediation_rule" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_rule_by_id.id
  http_method   = "DELETE"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
  request_parameters = { "method.request.path.rule_id" = true }
}

resource "aws_api_gateway_integration" "delete_remediation_rule" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.remediation_rule_by_id.id
  http_method             = aws_api_gateway_method.delete_remediation_rule.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}

# OPTIONS /remediation/rules/{rule_id}
resource "aws_api_gateway_method" "options_remediation_rule_by_id" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_rule_by_id.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "options_remediation_rule_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_rule_by_id.id
  http_method = aws_api_gateway_method.options_remediation_rule_by_id.http_method
  type        = "MOCK"
  request_templates = { "application/json" = "{\"statusCode\": 200}" }
}

resource "aws_api_gateway_method_response" "options_remediation_rule_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_rule_by_id.id
  http_method = aws_api_gateway_method.options_remediation_rule_by_id.http_method
  status_code = "200"
  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "options_remediation_rule_by_id" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  resource_id = aws_api_gateway_resource.remediation_rule_by_id.id
  http_method = aws_api_gateway_method.options_remediation_rule_by_id.http_method
  status_code = aws_api_gateway_method_response.options_remediation_rule_by_id.status_code
  response_parameters = local.cors_response_parameters
  response_templates  = local.cors_response_templates
  depends_on          = [aws_api_gateway_integration.options_remediation_rule_by_id]
}

# ===========================================================================
# /remediation/audit
# ===========================================================================
resource "aws_api_gateway_resource" "remediation_audit" {
  rest_api_id = aws_api_gateway_rest_api.radius.id
  parent_id   = aws_api_gateway_resource.remediation.id
  path_part   = "audit"
}

resource "aws_api_gateway_method" "get_remediation_audit" {
  rest_api_id   = aws_api_gateway_rest_api.radius.id
  resource_id   = aws_api_gateway_resource.remediation_audit.id
  http_method   = "GET"
  authorization = local.authorization
  authorizer_id = local.authorizer_id
}

resource "aws_api_gateway_integration" "get_remediation_audit" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.remediation_audit.id
  http_method             = aws_api_gateway_method.get_remediation_audit.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}
