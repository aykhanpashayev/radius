# EventBridge module for Radius
# Routes CloudTrail management events (IAM, STS, Organizations, EC2) to Event_Normalizer.

locals {
  common_tags = merge(
    {
      Module      = "eventbridge"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# EventBridge Rule — filter management events to Event_Normalizer
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_rule" "cloudtrail_management" {
  name        = "${var.prefix}-cloudtrail-management-events"
  description = "Route IAM, STS, Organizations, and EC2 management events to Event_Normalizer"

  event_pattern = jsonencode({
    source      = ["aws.iam", "aws.sts", "aws.organizations", "aws.ec2"]
    detail-type = ["AWS API Call via CloudTrail"]
  })

  tags = local.common_tags
}

# ---------------------------------------------------------------------------
# EventBridge Target — Event_Normalizer Lambda
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_event_target" "event_normalizer" {
  rule      = aws_cloudwatch_event_rule.cloudtrail_management.name
  target_id = "EventNormalizer"
  arn       = var.lambda_function_arns.event_normalizer

  retry_policy {
    maximum_event_age_in_seconds = 3600  # 1 hour
    maximum_retry_attempts       = 3
  }

  dead_letter_config {
    arn = aws_sqs_queue.eventbridge_dlq.arn
  }
}

# ---------------------------------------------------------------------------
# Lambda permission — allow EventBridge to invoke Event_Normalizer
# ---------------------------------------------------------------------------
resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_arns.event_normalizer
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.cloudtrail_management.arn
}

# ---------------------------------------------------------------------------
# Dead-Letter Queue for failed EventBridge deliveries
# ---------------------------------------------------------------------------
resource "aws_sqs_queue" "eventbridge_dlq" {
  name                      = "${var.prefix}-eventbridge-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = merge(local.common_tags, { Purpose = "eventbridge-dlq" })
}

# Allow EventBridge to send messages to the DLQ
resource "aws_sqs_queue_policy" "eventbridge_dlq" {
  queue_url = aws_sqs_queue.eventbridge_dlq.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgeDLQ"
        Effect = "Allow"
        Principal = {
          Service = "events.amazonaws.com"
        }
        Action   = "sqs:SendMessage"
        Resource = aws_sqs_queue.eventbridge_dlq.arn
        Condition = {
          ArnEquals = {
            "aws:SourceArn" = aws_cloudwatch_event_rule.cloudtrail_management.arn
          }
        }
      }
    ]
  })
}
