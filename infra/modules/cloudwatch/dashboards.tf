# CloudWatch dashboards for Radius.
# Four dashboards: Lambda, DynamoDB, API Gateway, EventBridge.

resource "aws_cloudwatch_dashboard" "lambda" {
  dashboard_name = "${var.prefix}-lambda"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Invocations"
          period = 300
          stat   = "Sum"
          metrics = [for name in local.lambda_names :
            ["AWS/Lambda", "Invocations", "FunctionName", name]
          ]
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "Lambda Errors"
          period = 300
          stat   = "Sum"
          metrics = [for name in local.lambda_names :
            ["AWS/Lambda", "Errors", "FunctionName", name]
          ]
        }
      },
      {
        type   = "metric"
        width  = 24
        height = 6
        properties = {
          title  = "Lambda Duration (p99)"
          period = 300
          stat   = "p99"
          metrics = [for name in local.lambda_names :
            ["AWS/Lambda", "Duration", "FunctionName", name]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_dashboard" "dynamodb" {
  dashboard_name = "${var.prefix}-dynamodb"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "DynamoDB Consumed Read Capacity"
          period = 300
          stat   = "Sum"
          metrics = [for name in values(var.dynamodb_table_names) :
            ["AWS/DynamoDB", "ConsumedReadCapacityUnits", "TableName", name]
          ]
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "DynamoDB Consumed Write Capacity"
          period = 300
          stat   = "Sum"
          metrics = [for name in values(var.dynamodb_table_names) :
            ["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", name]
          ]
        }
      },
      {
        type   = "metric"
        width  = 24
        height = 6
        properties = {
          title  = "DynamoDB Throttled Requests"
          period = 60
          stat   = "Sum"
          metrics = [for name in values(var.dynamodb_table_names) :
            ["AWS/DynamoDB", "ThrottledRequests", "TableName", name]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_dashboard" "api_gateway" {
  dashboard_name = "${var.prefix}-api-gateway"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 8
        height = 6
        properties = {
          title  = "API Gateway Request Count"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiName", var.api_gateway_name]
          ]
        }
      },
      {
        type   = "metric"
        width  = 8
        height = 6
        properties = {
          title  = "API Gateway Latency (p99)"
          period = 300
          stat   = "p99"
          metrics = [
            ["AWS/ApiGateway", "Latency", "ApiName", var.api_gateway_name]
          ]
        }
      },
      {
        type   = "metric"
        width  = 8
        height = 6
        properties = {
          title  = "API Gateway 4xx / 5xx Errors"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/ApiGateway", "4XXError", "ApiName", var.api_gateway_name],
            ["AWS/ApiGateway", "5XXError", "ApiName", var.api_gateway_name]
          ]
        }
      }
    ]
  })
}

resource "aws_cloudwatch_dashboard" "eventbridge" {
  dashboard_name = "${var.prefix}-eventbridge"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "EventBridge Rule Invocations"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/Events", "Invocations", "RuleName", "${var.prefix}-cloudtrail-management-events"]
          ]
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "EventBridge Failed Invocations"
          period = 300
          stat   = "Sum"
          metrics = [
            ["AWS/Events", "FailedInvocations", "RuleName", "${var.prefix}-cloudtrail-management-events"]
          ]
        }
      }
    ]
  })
}
