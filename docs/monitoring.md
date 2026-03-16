# Monitoring

## CloudWatch Dashboards

Four dashboards are provisioned automatically by the `cloudwatch` Terraform module.

| Dashboard | Metrics |
|---|---|
| `{prefix}-lambda` | Invocations, Errors, Duration (p99) per function |
| `{prefix}-dynamodb` | Consumed read/write capacity, throttled requests per table |
| `{prefix}-api-gateway` | Request count, latency (p99), 4xx/5xx error rates |
| `{prefix}-eventbridge` | Rule invocations, failed invocations |

Access dashboards at: `https://console.aws.amazon.com/cloudwatch/home#dashboards`

## CloudWatch Alarms

All alarms publish to the SNS Alert_Topic when triggered.

| Alarm | Condition | Period |
|---|---|---|
| `{prefix}-{fn}-error-rate` | Lambda error rate > 5% | 5 min |
| `{prefix}-{fn}-duration` | Lambda p99 duration > 24s | 5 min |
| `{prefix}-dynamodb-{table}-throttles` | DynamoDB throttled requests > 10 | 1 min |
| `{prefix}-{fn}-dlq-messages` | DLQ message count > 0 | 1 min |
| `{prefix}-api-gateway-5xx` | API Gateway 5xx rate > 1% | 5 min |

## Structured Logging

All Lambda functions emit structured JSON logs to CloudWatch Logs via `backend/common/logging_utils.py`.

Every log record includes:
- `timestamp` — ISO 8601 UTC
- `level` — INFO, WARNING, or ERROR
- `logger` — module name
- `message` — human-readable description
- `correlation_id` — UUID v4 generated per invocation (propagated across async calls)

Log groups follow the pattern `/aws/lambda/{prefix}-{function-name}`.

Retention: 7 days (dev), 30 days (prod).

## Correlation ID Tracing

Each Lambda invocation generates a `correlation_id` at entry. This ID is:
- Included in every log record for that invocation
- Passed to downstream async invocations in the event payload
- Logged on errors with full stack trace via `log_error()`

To trace a request end-to-end, search CloudWatch Logs Insights across all log groups:

```
fields @timestamp, @message
| filter correlation_id = "your-correlation-id-here"
| sort @timestamp asc
```

## Troubleshooting Common Issues

**Lambda errors appearing in DLQ:**
1. Check the DLQ alarm — it fires on any message count > 0
2. Open the DLQ in SQS console and inspect the message body
3. Search CloudWatch Logs for the `correlation_id` in the failed event
4. Common causes: DynamoDB throttling, malformed event payload, IAM permission missing

**DynamoDB throttling:**
- On-demand tables auto-scale but can throttle during sudden traffic spikes
- Check the DynamoDB dashboard for consumed vs provisioned capacity
- The `dynamodb_utils.py` retry logic handles transient throttles with exponential backoff (3 retries, 100ms base delay)

**API Gateway 5xx errors:**
- Check the API Gateway dashboard for the affected endpoint
- Search Lambda logs for the `requestId` from the API Gateway access log
- Common causes: Lambda timeout, unhandled exception in handler, DynamoDB error

**CloudTrail events not appearing in DynamoDB:**
- Verify CloudTrail trail is logging: `aws cloudtrail get-trail-status --name {prefix}-trail`
- Verify EventBridge rule is enabled: check the EventBridge console
- Check Event_Normalizer DLQ for failed events
- Verify Event_Normalizer IAM role has `dynamodb:PutItem` on the Event_Summary table
