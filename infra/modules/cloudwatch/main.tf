# CloudWatch module for Radius observability.
# Log groups for all Lambda functions (log groups for Lambda itself are
# managed in the Lambda module; these are additional application log groups).

locals {
  common_tags = merge(
    {
      Module      = "cloudwatch"
      Environment = var.environment
    },
    var.tags
  )

  lambda_names = [
    var.lambda_function_names.event_normalizer,
    var.lambda_function_names.detection_engine,
    var.lambda_function_names.incident_processor,
    var.lambda_function_names.identity_collector,
    var.lambda_function_names.score_engine,
    var.lambda_function_names.api_handler,
  ]
}
