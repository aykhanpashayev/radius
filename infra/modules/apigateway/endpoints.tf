# API Gateway endpoint definitions for Radius
# 10 operations across 5 resource groups.
# All use Lambda proxy integration pointing to API_Handler.

locals {
  lambda_uri = "arn:aws:apigateway:${data.aws_region.current.name}:lambda:path/2015-03-31/functions/${var.lambda_function_arn}/invocations"
}

data "aws_region" "current" {}

# ---------------------------------------------------------------------------
# Helper: CORS OPTIONS method (shared mock integration)
# ---------------------------------------------------------------------------
# Not defined per-resource here to keep the file concise.
# CORS headers are returned by the Lambda proxy response.

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
  authorization = "NONE"
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
  authorization = "NONE"

  request_parameters = {
    "method.request.path.arn" = true
  }
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
  authorization = "NONE"
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
  authorization = "NONE"

  request_parameters = {
    "method.request.path.arn" = true
  }
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
  authorization = "NONE"
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
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id" = true
  }
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
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id" = true
  }
}

resource "aws_api_gateway_integration" "patch_incident_by_id" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.incident_by_id.id
  http_method             = aws_api_gateway_method.patch_incident_by_id.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
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
  authorization = "NONE"
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
  authorization = "NONE"

  request_parameters = {
    "method.request.path.id" = true
  }
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
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "get_trust_relationships" {
  rest_api_id             = aws_api_gateway_rest_api.radius.id
  resource_id             = aws_api_gateway_resource.trust_relationships.id
  http_method             = aws_api_gateway_method.get_trust_relationships.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = local.lambda_uri
}
