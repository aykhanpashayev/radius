# CloudWatch alarms for Radius operational monitoring.
# Covers Lambda errors/duration, DynamoDB throttles, DLQ depth, API Gateway 5xx.

locals {
  lambda_function_list = {
    event_normalizer   = var.lambda_function_names.event_normalizer
    detection_engine   = var.lambda_function_names.detection_engine
    incident_processor = var.lambda_function_names.incident_processor
    identity_collector = var.lambda_function_names.identity_collector
    score_engine       = var.lambda_function_names.score_engine
    api_handler        = var.lambda_function_names.api_handler
  }
}

# ---------------------------------------------------------------------------
# Lambda error rate > 5% over 5 minutes (one alarm per function)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_error_rate" {
  for_each = local.lambda_function_list

  alarm_name          = "${var.prefix}-${each.key}-error-rate"
  alarm_description   = "Lambda ${each.value} error rate exceeded 5%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 5
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "errors / MAX([errors, invocations]) * 100"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      namespace   = "AWS/Lambda"
      metric_name = "Errors"
      dimensions  = { FunctionName = each.value }
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "invocations"
    metric {
      namespace   = "AWS/Lambda"
      metric_name = "Invocations"
      dimensions  = { FunctionName = each.value }
      period      = 300
      stat        = "Sum"
    }
  }

  alarm_actions = [var.alarm_sns_topic_arn]
  ok_actions    = [var.alarm_sns_topic_arn]
  tags          = local.common_tags
}

# ---------------------------------------------------------------------------
# Lambda duration approaching timeout (>80% of configured timeout)
# Using a fixed 24s threshold (80% of the most common 30s timeout).
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "lambda_duration" {
  for_each = local.lambda_function_list

  alarm_name          = "${var.prefix}-${each.key}-duration"
  alarm_description   = "Lambda ${each.value} p99 duration is high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  threshold           = 24000 # 24 seconds in ms
  treat_missing_data  = "notBreaching"

  namespace          = "AWS/Lambda"
  metric_name        = "Duration"
  dimensions         = { FunctionName = each.value }
  period             = 300
  extended_statistic = "p99"

  alarm_actions = [var.alarm_sns_topic_arn]
  tags          = local.common_tags
}

# ---------------------------------------------------------------------------
# DynamoDB throttled requests > 10 per minute
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "dynamodb_throttles" {
  for_each = var.dynamodb_table_names

  alarm_name          = "${var.prefix}-dynamodb-${each.key}-throttles"
  alarm_description   = "DynamoDB table ${each.value} throttled requests exceeded 10/min"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 10
  treat_missing_data  = "notBreaching"

  namespace   = "AWS/DynamoDB"
  metric_name = "ThrottledRequests"
  dimensions  = { TableName = each.value }
  period      = 60
  statistic   = "Sum"

  alarm_actions = [var.alarm_sns_topic_arn]
  tags          = local.common_tags
}

# ---------------------------------------------------------------------------
# DLQ message count > 0 (any failed async invocation)
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  for_each = var.dlq_arns

  alarm_name          = "${var.prefix}-${each.key}-dlq-messages"
  alarm_description   = "Dead-letter queue ${each.key} has messages — investigate failed invocations"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 0
  treat_missing_data  = "notBreaching"

  namespace   = "AWS/SQS"
  metric_name = "ApproximateNumberOfMessagesVisible"
  dimensions  = { QueueName = each.value }
  period      = 60
  statistic   = "Sum"

  alarm_actions = [var.alarm_sns_topic_arn]
  tags          = local.common_tags
}

# ---------------------------------------------------------------------------
# API Gateway 5xx error rate > 1% over 5 minutes
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_metric_alarm" "api_gateway_5xx" {
  alarm_name          = "${var.prefix}-api-gateway-5xx"
  alarm_description   = "API Gateway 5xx error rate exceeded 1%"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  threshold           = 1
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "error_rate"
    expression  = "errors / MAX([errors, requests]) * 100"
    label       = "5xx Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "errors"
    metric {
      namespace   = "AWS/ApiGateway"
      metric_name = "5XXError"
      dimensions  = { ApiName = var.api_gateway_name }
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "requests"
    metric {
      namespace   = "AWS/ApiGateway"
      metric_name = "Count"
      dimensions  = { ApiName = var.api_gateway_name }
      period      = 300
      stat        = "Sum"
    }
  }

  alarm_actions = [var.alarm_sns_topic_arn]
  ok_actions    = [var.alarm_sns_topic_arn]
  tags          = local.common_tags
}
