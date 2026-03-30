# Monitoring

## Table of Contents

- [CloudWatch Dashboards](#cloudwatch-dashboards)
- [CloudWatch Alarms](#cloudwatch-alarms)
- [Structured Logging](#structured-logging)
- [Correlation ID Propagation](#correlation-id-propagation)
- [Example CloudWatch Logs Insights Queries](#example-cloudwatch-logs-insights-queries)
- [Troubleshooting Common Issues](#troubleshooting-common-issues)

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

**Infrastructure alarms:**

| Alarm | Condition | Period |
|---|---|---|
| `{prefix}-{fn}-error-rate` | Lambda error rate > 5% | 5 min |
| `{prefix}-{fn}-duration` | Lambda p99 duration > 24s | 5 min |
| `{prefix}-dynamodb-{table}-throttles` | DynamoDB throttled requests > 10 | 1 min |
| `{prefix}-{fn}-dlq-messages` | DLQ message count > 0 | 1 min |
| `{prefix}-api-gateway-5xx` | API Gateway 5xx rate > 1% | 5 min |

**Business-logic alarms** (detect silent pipeline failures):

| Alarm | Condition | Period | Missing data |
|---|---|---|---|
| `{prefix}-no-scores-written-6h` | `ScoresWritten` sum < 1 | 6 hours | breaching |
| `{prefix}-no-incidents-72h` | `IncidentsCreated` sum < 1 | 72 hours | breaching |
| `{prefix}-scoring-failure-rate` | `ScoringFailures / ScoresWritten` > 10% | 1 hour | not breaching |

Business-logic metrics are emitted to the `Radius` CloudWatch namespace by the Lambda functions themselves via `put_metric()` in `backend/common/logging_utils.py`.

## Structured Logging

All Lambda functions emit structured JSON logs to CloudWatch Logs via `backend/common/logging_utils.py`.

Every log record includes:
- `timestamp` — ISO 8601 UTC
- `level` — INFO, WARNING, or ERROR
- `logger` — module name
- `message` — human-readable description
- `correlation_id` — UUID v4 generated per invocation (propagated across async calls)

Log groups follow the pattern `/aws/lambda/{prefix}-{function-name}`.

Retention: 7 days (dev), 365 days (prod).

The log level is controlled by the `LOG_LEVEL` environment variable (default `INFO`). Set `log_level = "DEBUG"` in `terraform.tfvars` to enable verbose logging without a code redeploy.

### Log Groups and Fields

| Log group | Additional structured fields |
|---|---|
| `/aws/lambda/{env}-event-normalizer` | `event_id`, `identity_arn`, `event_type` |
| `/aws/lambda/{env}-detection-engine` | `event_id`, `identity_arn`, `findings_count` |
| `/aws/lambda/{env}-incident-processor` | `incident_id`, `identity_arn`, `detection_type`, `severity` |
| `/aws/lambda/{env}-identity-collector` | `identity_arn`, `identity_type`, `account_id` |
| `/aws/lambda/{env}-score-engine` | `identity_arn`, `score_value`, `severity_level` |
| `/aws/lambda/{env}-api-handler` | `http_method`, `path`, `status_code`, `duration_ms` |
| `/aws/lambda/{env}-remediation-engine` | `function_name`, `correlation_id`, `incident_id`, `identity_arn`, `risk_mode`, `actions_executed`, `actions_suppressed` |

## Correlation ID Propagation

Every invocation of Event_Normalizer generates a `correlation_id` (UUID v4) at entry. This ID travels through the entire async pipeline so that a single CloudTrail event can be traced end-to-end across all log groups.

**Propagation path:**

1. **Event_Normalizer** — generates `correlation_id`, includes it in every log record for that invocation, and embeds it in the payload passed to Detection_Engine via async Lambda invoke.
2. **Detection_Engine** — reads `correlation_id` from the invocation payload, includes it in all log records, and passes it forward in the payload to Incident_Processor.
3. **Incident_Processor** — reads `correlation_id` from the payload, logs it with every record, and includes it in the async invoke payload sent to Remediation_Engine.
4. **Remediation_Engine** — reads `correlation_id` from the payload and logs it with every audit and outcome record.

Because `correlation_id` is present in every log record across all four functions, a single Logs Insights query across all log groups can reconstruct the complete execution trace for any event.

**Tracing a request end-to-end in CloudWatch Logs Insights:**

Select all relevant log groups (`/aws/lambda/{env}-event-normalizer`, `-detection-engine`, `-incident-processor`, `-remediation-engine`) and run:

```
fields @timestamp, @logStream, @message
| filter correlation_id = "your-correlation-id-here"
| sort @timestamp asc
```

## Example CloudWatch Logs Insights Queries

### Find all log entries for a given correlation_id

Use this to trace a single CloudTrail event through the full pipeline. Select all Lambda log groups.

```
fields @timestamp, @logStream, level, message, incident_id, identity_arn
| filter correlation_id = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
| sort @timestamp asc
```

### Find all incidents created in the last hour

Run against `/aws/lambda/{env}-incident-processor`.

```
fields @timestamp, incident_id, identity_arn, detection_type, severity
| filter message = "Incident created"
| filter @timestamp >= ago(1h)
| sort @timestamp desc
```

### Find all remediation actions executed for a given identity_arn

Run against `/aws/lambda/{env}-remediation-engine`.

```
fields @timestamp, incident_id, action_name, outcome, risk_mode, reason
| filter identity_arn = "arn:aws:iam::123456789012:user/attacker"
| filter outcome = "executed"
| sort @timestamp desc
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
