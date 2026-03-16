# IAM roles and least-privilege policies for all Lambda functions.
# Each function gets its own role scoped to only the resources it needs.

data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# Event_Normalizer
# Reads from EventBridge (implicit via trigger), writes Event_Summary,
# invokes Detection_Engine and Identity_Collector asynchronously.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "event_normalizer" {
  name               = "${var.prefix}-event-normalizer-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "event-normalizer" })
}

resource "aws_iam_role_policy" "event_normalizer" {
  name = "${var.prefix}-event-normalizer-policy"
  role = aws_iam_role.event_normalizer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.event_normalizer.arn}:*"
      },
      {
        Sid    = "WriteEventSummary"
        Effect = "Allow"
        Action = ["dynamodb:PutItem"]
        Resource = var.dynamodb_table_arns.event_summary
      },
      {
        Sid    = "InvokeDownstream"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.detection_engine.arn,
          aws_lambda_function.identity_collector.arn,
        ]
      },
      {
        Sid    = "DLQ"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.event_normalizer_dlq.arn
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Detection_Engine (Placeholder)
# Reads Event_Summary, invokes Incident_Processor.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "detection_engine" {
  name               = "${var.prefix}-detection-engine-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "detection-engine" })
}

resource "aws_iam_role_policy" "detection_engine" {
  name = "${var.prefix}-detection-engine-policy"
  role = aws_iam_role.detection_engine.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.detection_engine.arn}:*"
      },
      {
        Sid    = "ReadEventSummary"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query"]
        Resource = concat(
          [var.dynamodb_table_arns.event_summary],
          var.dynamodb_gsi_arns["event_summary"]
        )
      },
      {
        Sid    = "InvokeIncidentProcessor"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.incident_processor.arn
      },
      {
        Sid    = "DLQ"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.detection_engine_dlq.arn
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Incident_Processor
# Writes Incident table, publishes to SNS Alert_Topic.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "incident_processor" {
  name               = "${var.prefix}-incident-processor-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "incident-processor" })
}

resource "aws_iam_role_policy" "incident_processor" {
  name = "${var.prefix}-incident-processor-policy"
  role = aws_iam_role.incident_processor.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.incident_processor.arn}:*"
      },
      {
        Sid    = "WriteIncident"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
        Resource = concat(
          [var.dynamodb_table_arns.incident],
          var.dynamodb_gsi_arns["incident"]
        )
      },
      {
        Sid    = "PublishSNS"
        Effect = "Allow"
        Action = ["sns:Publish"]
        Resource = var.sns_topic_arn
      },
      {
        Sid    = "DLQ"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.incident_processor_dlq.arn
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Identity_Collector
# Writes Identity_Profile and Trust_Relationship tables.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "identity_collector" {
  name               = "${var.prefix}-identity-collector-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "identity-collector" })
}

resource "aws_iam_role_policy" "identity_collector" {
  name = "${var.prefix}-identity-collector-policy"
  role = aws_iam_role.identity_collector.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.identity_collector.arn}:*"
      },
      {
        Sid    = "WriteIdentityProfile"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.identity_profile
      },
      {
        Sid    = "WriteTrustRelationship"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.trust_relationship
      },
      {
        Sid    = "DLQ"
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.identity_collector_dlq.arn
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Score_Engine (Placeholder)
# Reads Identity_Profile, writes Blast_Radius_Score.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "score_engine" {
  name               = "${var.prefix}-score-engine-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "score-engine" })
}

resource "aws_iam_role_policy" "score_engine" {
  name = "${var.prefix}-score-engine-policy"
  role = aws_iam_role.score_engine.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.score_engine.arn}:*"
      },
      {
        Sid    = "ReadIdentityProfile"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
        Resource = concat(
          [var.dynamodb_table_arns.identity_profile],
          var.dynamodb_gsi_arns["identity_profile"]
        )
      },
      {
        Sid    = "WriteBlastRadiusScore"
        Effect = "Allow"
        Action = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.blast_radius_score
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# API_Handler
# Reads all tables, writes Incident table (status updates only).
# ---------------------------------------------------------------------------
resource "aws_iam_role" "api_handler" {
  name               = "${var.prefix}-api-handler-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "api-handler" })
}

resource "aws_iam_role_policy" "api_handler" {
  name = "${var.prefix}-api-handler-policy"
  role = aws_iam_role.api_handler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api_handler.arn}:*"
      },
      {
        Sid    = "ReadAllTables"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query"]
        Resource = concat(
          [
            var.dynamodb_table_arns.identity_profile,
            var.dynamodb_table_arns.blast_radius_score,
            var.dynamodb_table_arns.incident,
            var.dynamodb_table_arns.event_summary,
            var.dynamodb_table_arns.trust_relationship,
          ],
          var.dynamodb_gsi_arns["identity_profile"],
          var.dynamodb_gsi_arns["blast_radius_score"],
          var.dynamodb_gsi_arns["incident"],
          var.dynamodb_gsi_arns["event_summary"],
          var.dynamodb_gsi_arns["trust_relationship"],
        )
      },
      {
        Sid    = "UpdateIncidentStatus"
        Effect = "Allow"
        Action = ["dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.incident
      },
      {
        Sid    = "KMS"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}
