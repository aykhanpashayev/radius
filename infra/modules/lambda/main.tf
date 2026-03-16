# Lambda functions for Radius
# Six functions: Event_Normalizer, Detection_Engine, Incident_Processor,
# Identity_Collector, Score_Engine, API_Handler.
# All use Python 3.11 on arm64. Event-driven functions have DLQs.

locals {
  common_tags = merge(
    {
      Module      = "lambda"
      Environment = var.environment
    },
    var.tags
  )
}

# ---------------------------------------------------------------------------
# Dead-Letter Queues (event-driven functions only)
# API_Handler and Score_Engine are excluded — they are synchronous.
# ---------------------------------------------------------------------------
resource "aws_sqs_queue" "event_normalizer_dlq" {
  name                      = "${var.prefix}-event-normalizer-dlq"
  message_retention_seconds = 1209600 # 14 days
  tags                      = merge(local.common_tags, { Function = "event-normalizer" })
}

resource "aws_sqs_queue" "detection_engine_dlq" {
  name                      = "${var.prefix}-detection-engine-dlq"
  message_retention_seconds = 1209600
  tags                      = merge(local.common_tags, { Function = "detection-engine" })
}

resource "aws_sqs_queue" "incident_processor_dlq" {
  name                      = "${var.prefix}-incident-processor-dlq"
  message_retention_seconds = 1209600
  tags                      = merge(local.common_tags, { Function = "incident-processor" })
}

resource "aws_sqs_queue" "identity_collector_dlq" {
  name                      = "${var.prefix}-identity-collector-dlq"
  message_retention_seconds = 1209600
  tags                      = merge(local.common_tags, { Function = "identity-collector" })
}

# ---------------------------------------------------------------------------
# CloudWatch Log Groups
# Created explicitly so retention is managed by Terraform.
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "event_normalizer" {
  name              = "/aws/lambda/${var.prefix}-event-normalizer"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Function = "event-normalizer" })
}

resource "aws_cloudwatch_log_group" "detection_engine" {
  name              = "/aws/lambda/${var.prefix}-detection-engine"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Function = "detection-engine" })
}

resource "aws_cloudwatch_log_group" "incident_processor" {
  name              = "/aws/lambda/${var.prefix}-incident-processor"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Function = "incident-processor" })
}

resource "aws_cloudwatch_log_group" "identity_collector" {
  name              = "/aws/lambda/${var.prefix}-identity-collector"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Function = "identity-collector" })
}

resource "aws_cloudwatch_log_group" "score_engine" {
  name              = "/aws/lambda/${var.prefix}-score-engine"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Function = "score-engine" })
}

resource "aws_cloudwatch_log_group" "api_handler" {
  name              = "/aws/lambda/${var.prefix}-api-handler"
  retention_in_days = var.log_retention_days
  tags              = merge(local.common_tags, { Function = "api-handler" })
}

# ---------------------------------------------------------------------------
# Lambda Functions
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "event_normalizer" {
  function_name = "${var.prefix}-event-normalizer"
  role          = aws_iam_role.event_normalizer.arn
  runtime       = "python3.11"
  architectures = ["arm64"]
  handler       = "handler.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = "functions/event_normalizer.zip"
  timeout       = var.timeout_configs.event_normalizer
  memory_size   = var.function_configs.event_normalizer

  reserved_concurrent_executions = var.concurrency_limit

  kms_key_arn = var.kms_key_arn

  environment {
    variables = {
      ENVIRONMENT                  = var.environment
      AWS_ACCOUNT_REGION           = var.aws_region
      EVENT_SUMMARY_TABLE          = var.dynamodb_table_names.event_summary
      DETECTION_ENGINE_ARN         = aws_lambda_function.detection_engine.arn
      IDENTITY_COLLECTOR_ARN       = aws_lambda_function.identity_collector.arn
      SCORE_ENGINE_FUNCTION_NAME   = aws_lambda_function.score_engine.function_name
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.event_normalizer_dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.event_normalizer]

  tags = merge(local.common_tags, { Function = "event-normalizer" })
}

resource "aws_lambda_function" "detection_engine" {
  function_name = "${var.prefix}-detection-engine"
  role          = aws_iam_role.detection_engine.arn
  runtime       = "python3.11"
  architectures = ["arm64"]
  handler       = "handler.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = "functions/detection_engine.zip"
  timeout       = var.timeout_configs.detection_engine
  memory_size   = var.function_configs.detection_engine

  reserved_concurrent_executions = var.concurrency_limit

  kms_key_arn = var.kms_key_arn

  environment {
    variables = {
      ENVIRONMENT              = var.environment
      AWS_ACCOUNT_REGION       = var.aws_region
      EVENT_SUMMARY_TABLE      = var.dynamodb_table_names.event_summary
      INCIDENT_PROCESSOR_ARN   = aws_lambda_function.incident_processor.arn
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.detection_engine_dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.detection_engine]

  tags = merge(local.common_tags, { Function = "detection-engine" })
}

resource "aws_lambda_function" "incident_processor" {
  function_name = "${var.prefix}-incident-processor"
  role          = aws_iam_role.incident_processor.arn
  runtime       = "python3.11"
  architectures = ["arm64"]
  handler       = "handler.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = "functions/incident_processor.zip"
  timeout       = var.timeout_configs.incident_processor
  memory_size   = var.function_configs.incident_processor

  reserved_concurrent_executions = var.concurrency_limit

  kms_key_arn = var.kms_key_arn

  environment {
    variables = {
      ENVIRONMENT      = var.environment
      AWS_ACCOUNT_REGION = var.aws_region
      INCIDENT_TABLE   = var.dynamodb_table_names.incident
      SNS_TOPIC_ARN    = var.sns_topic_arn
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.incident_processor_dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.incident_processor]

  tags = merge(local.common_tags, { Function = "incident-processor" })
}

resource "aws_lambda_function" "identity_collector" {
  function_name = "${var.prefix}-identity-collector"
  role          = aws_iam_role.identity_collector.arn
  runtime       = "python3.11"
  architectures = ["arm64"]
  handler       = "handler.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = "functions/identity_collector.zip"
  timeout       = var.timeout_configs.identity_collector
  memory_size   = var.function_configs.identity_collector

  reserved_concurrent_executions = var.concurrency_limit

  kms_key_arn = var.kms_key_arn

  environment {
    variables = {
      ENVIRONMENT              = var.environment
      AWS_ACCOUNT_REGION       = var.aws_region
      IDENTITY_PROFILE_TABLE   = var.dynamodb_table_names.identity_profile
      TRUST_RELATIONSHIP_TABLE = var.dynamodb_table_names.trust_relationship
    }
  }

  dead_letter_config {
    target_arn = aws_sqs_queue.identity_collector_dlq.arn
  }

  depends_on = [aws_cloudwatch_log_group.identity_collector]

  tags = merge(local.common_tags, { Function = "identity-collector" })
}

resource "aws_lambda_function" "score_engine" {
  function_name = "${var.prefix}-score-engine"
  role          = aws_iam_role.score_engine.arn
  runtime       = "python3.11"
  architectures = ["arm64"]
  handler       = "handler.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = "functions/score_engine.zip"
  timeout       = var.timeout_configs.score_engine
  memory_size   = var.function_configs.score_engine

  kms_key_arn = var.kms_key_arn

  environment {
    variables = {
      ENVIRONMENT              = var.environment
      AWS_ACCOUNT_REGION       = var.aws_region
      IDENTITY_PROFILE_TABLE   = var.dynamodb_table_names.identity_profile
      BLAST_RADIUS_SCORE_TABLE = var.dynamodb_table_names.blast_radius_score
    }
  }

  depends_on = [aws_cloudwatch_log_group.score_engine]

  tags = merge(local.common_tags, { Function = "score-engine" })
}

resource "aws_lambda_function" "api_handler" {
  function_name = "${var.prefix}-api-handler"
  role          = aws_iam_role.api_handler.arn
  runtime       = "python3.11"
  architectures = ["arm64"]
  handler       = "handler.lambda_handler"
  s3_bucket     = var.lambda_s3_bucket
  s3_key        = "functions/api_handler.zip"
  timeout       = var.timeout_configs.api_handler
  memory_size   = var.function_configs.api_handler

  kms_key_arn = var.kms_key_arn

  environment {
    variables = {
      ENVIRONMENT              = var.environment
      AWS_ACCOUNT_REGION       = var.aws_region
      IDENTITY_PROFILE_TABLE   = var.dynamodb_table_names.identity_profile
      BLAST_RADIUS_SCORE_TABLE = var.dynamodb_table_names.blast_radius_score
      INCIDENT_TABLE           = var.dynamodb_table_names.incident
      EVENT_SUMMARY_TABLE      = var.dynamodb_table_names.event_summary
      TRUST_RELATIONSHIP_TABLE = var.dynamodb_table_names.trust_relationship
    }
  }

  depends_on = [aws_cloudwatch_log_group.api_handler]

  tags = merge(local.common_tags, { Function = "api-handler" })
}
