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
# VPC access policy — attached to all Lambda roles when vpc_config is set.
# Grants the EC2 permissions Lambda needs to create and clean up ENIs.
# ---------------------------------------------------------------------------
resource "aws_iam_policy" "lambda_vpc_access" {
  count = var.vpc_config != null ? 1 : 0
  name  = "${var.prefix}-lambda-vpc-access"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "LambdaVPCAccess"
      Effect = "Allow"
      Action = [
        "ec2:CreateNetworkInterface",
        "ec2:DescribeNetworkInterfaces",
        "ec2:DeleteNetworkInterface",
        "ec2:AssignPrivateIpAddresses",
        "ec2:UnassignPrivateIpAddresses",
      ]
      Resource = "*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "event_normalizer_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.event_normalizer.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
}

resource "aws_iam_role_policy_attachment" "detection_engine_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.detection_engine.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
}

resource "aws_iam_role_policy_attachment" "incident_processor_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.incident_processor.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
}

resource "aws_iam_role_policy_attachment" "identity_collector_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.identity_collector.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
}

resource "aws_iam_role_policy_attachment" "score_engine_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.score_engine.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
}

resource "aws_iam_role_policy_attachment" "api_handler_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.api_handler.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
}

resource "aws_iam_role_policy_attachment" "remediation_engine_vpc" {
  count      = var.vpc_config != null ? 1 : 0
  role       = aws_iam_role.remediation_engine.name
  policy_arn = aws_iam_policy.lambda_vpc_access[0].arn
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
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.event_normalizer.arn}:*"
      },
      {
        Sid      = "WriteEventSummary"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem"]
        Resource = var.dynamodb_table_arns.event_summary
      },
      {
        Sid    = "InvokeDownstream"
        Effect = "Allow"
        Action = ["lambda:InvokeFunction"]
        Resource = [
          aws_lambda_function.detection_engine.arn,
          aws_lambda_function.identity_collector.arn,
          aws_lambda_function.score_engine.arn,
        ]
      },
      {
        Sid      = "DLQ"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.event_normalizer_dlq.arn
      },
      {
        Sid      = "KMS"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
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
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
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
        Sid      = "InvokeIncidentProcessor"
        Effect   = "Allow"
        Action   = ["lambda:InvokeFunction"]
        Resource = aws_lambda_function.incident_processor.arn
      },
      {
        Sid      = "DLQ"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.detection_engine_dlq.arn
      },
      {
        Sid      = "KMS"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
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
    Statement = concat(
      [
        {
          Sid      = "CloudWatchLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${aws_cloudwatch_log_group.incident_processor.arn}:*"
        },
        {
          Sid    = "WriteIncident"
          Effect = "Allow"
          Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
          Resource = concat(
            [var.dynamodb_table_arns.incident],
            var.dynamodb_gsi_arns["incident"]
          )
        },
        {
          Sid      = "PublishSNS"
          Effect   = "Allow"
          Action   = ["sns:Publish"]
          Resource = var.sns_topic_arn
        },
        {
          Sid      = "InvokeRemediationEngine"
          Effect   = "Allow"
          Action   = ["lambda:InvokeFunction"]
          Resource = aws_lambda_function.remediation_engine.arn
        },
        {
          Sid      = "DLQ"
          Effect   = "Allow"
          Action   = ["sqs:SendMessage"]
          Resource = aws_sqs_queue.incident_processor_dlq.arn
        },
        {
          Sid      = "KMS"
          Effect   = "Allow"
          Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
          Resource = var.kms_key_arn
        },
      ],
      length(var.secret_arns) > 0 ? [
        {
          Sid      = "ReadAlertingSecrets"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = var.secret_arns
        }
      ] : []
    )
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
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.identity_collector.arn}:*"
      },
      {
        Sid      = "WriteIdentityProfile"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.identity_profile
      },
      {
        Sid      = "WriteTrustRelationship"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.trust_relationship
      },
      {
        Sid      = "DLQ"
        Effect   = "Allow"
        Action   = ["sqs:SendMessage"]
        Resource = aws_sqs_queue.identity_collector_dlq.arn
      },
      {
        Sid      = "KMS"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
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
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
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
        Sid      = "WriteBlastRadiusScore"
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem"]
        Resource = var.dynamodb_table_arns.blast_radius_score
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
        Sid    = "ReadTrustRelationship"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query"]
        Resource = concat(
          [var.dynamodb_table_arns.trust_relationship],
          var.dynamodb_gsi_arns["trust_relationship"]
        )
      },
      {
        Sid    = "ReadIncident"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query"]
        Resource = concat(
          [var.dynamodb_table_arns.incident],
          var.dynamodb_gsi_arns["incident"]
        )
      },
      {
        Sid      = "KMS"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
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
        Sid      = "CloudWatchLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api_handler.arn}:*"
      },
      {
        Sid    = "ReadAllTables"
        Effect = "Allow"
        Action = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
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
        Sid      = "UpdateIncidentStatus"
        Effect   = "Allow"
        Action   = ["dynamodb:UpdateItem"]
        Resource = var.dynamodb_table_arns.incident
      },
      {
        Sid    = "RemediationConfigAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
        ]
        Resource = var.dynamodb_table_arns.remediation_config
      },
      {
        Sid    = "RemediationAuditAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = concat(
          [var.dynamodb_table_arns.remediation_audit_log],
          var.dynamodb_gsi_arns["remediation_audit_log"]
        )
      },
      {
        Sid      = "KMS"
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
        Resource = var.kms_key_arn
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Remediation_Engine
# Executes IAM remediation actions, reads/writes remediation tables,
# publishes to Remediation_Topic SNS.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "remediation_engine" {
  name               = "${var.prefix}-remediation-engine-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
  tags               = merge(local.common_tags, { Function = "remediation-engine" })
}

resource "aws_iam_role_policy" "remediation_engine" {
  name = "${var.prefix}-remediation-engine-policy"
  role = aws_iam_role.remediation_engine.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = concat(
      [
        {
          Sid      = "CloudWatchLogs"
          Effect   = "Allow"
          Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
          Resource = "${aws_cloudwatch_log_group.remediation_engine.arn}:*"
        },
        {
          Sid      = "DLQ"
          Effect   = "Allow"
          Action   = ["sqs:SendMessage"]
          Resource = aws_sqs_queue.remediation_engine_dlq.arn
        },
        {
          Sid    = "IAMRemediation"
          Effect = "Allow"
          Action = [
            "iam:ListAccessKeys",
            "iam:UpdateAccessKey",
            "iam:DeleteLoginProfile",
            "iam:ListAttachedUserPolicies",
            "iam:ListAttachedRolePolicies",
            "iam:ListUserPolicies",
            "iam:ListRolePolicies",
            "iam:GetUserPolicy",
            "iam:GetRolePolicy",
            "iam:DetachUserPolicy",
            "iam:DetachRolePolicy",
            "iam:DeleteUserPolicy",
            "iam:DeleteRolePolicy",
            "iam:GetRole",
            "iam:UpdateAssumeRolePolicy",
            "iam:PutUserPolicy",
            "iam:PutRolePolicy",
          ]
          Resource = "*"
        },
        {
          Sid    = "RemediationConfigTable"
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:Query",
          ]
          Resource = var.dynamodb_table_arns.remediation_config
        },
        {
          Sid    = "RemediationAuditTable"
          Effect = "Allow"
          Action = [
            "dynamodb:GetItem",
            "dynamodb:PutItem",
            "dynamodb:UpdateItem",
            "dynamodb:Query",
          ]
          Resource = concat(
            [var.dynamodb_table_arns.remediation_audit_log],
            var.dynamodb_gsi_arns["remediation_audit_log"]
          )
        },
        {
          Sid      = "PublishRemediationTopic"
          Effect   = "Allow"
          Action   = ["sns:Publish"]
          Resource = var.remediation_topic_arn
        },
        {
          Sid      = "KMS"
          Effect   = "Allow"
          Action   = ["kms:Decrypt", "kms:GenerateDataKey*"]
          Resource = var.kms_key_arn
        },
      ],
      length(var.secret_arns) > 0 ? [
        {
          Sid      = "ReadAlertingSecrets"
          Effect   = "Allow"
          Action   = ["secretsmanager:GetSecretValue"]
          Resource = var.secret_arns
        }
      ] : []
    )
  })
}
