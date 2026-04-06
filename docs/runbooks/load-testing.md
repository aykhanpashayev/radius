# Load Testing Runbook

## Purpose

Run load tests after major releases or infrastructure changes to:

1. Establish and update **performance baselines** (p50/p95/p99 latencies)
2. Validate that **CloudWatch alarm thresholds** match real-world traffic (the current 24 000 ms duration threshold is a starting estimate)
3. Confirm that **VPC endpoints and Lambda cold-start times** are acceptable in prod
4. Detect regressions before they affect live users

---

## Prerequisites

- A deployed Radius environment (`dev` or `prod`)
- A valid Cognito JWT for that environment (see "Obtaining a JWT" below)
- Python 3.11 and `pip` (locust will be installed automatically)
- AWS CLI configured with SSM read access

---

## Obtaining a JWT

**Option A — via the load-test.sh script (automatic)**

Pass `--username` and `--password` to have the script call Cognito's USER_PASSWORD_AUTH flow:

```bash
bash scripts/load-test.sh \
  --env prod \
  --username analyst@example.com \
  --password "YourPassword"
```

**Option B — from the browser (manual)**

1. Log into the Radius dashboard
2. Open DevTools → Network → click any API request
3. Copy the `Authorization` header value (the part after `Bearer `)
4. Pass it with `--jwt "<token>"`

---

## Running a Load Test

### Quick smoke test (5 users, 2 minutes)

```bash
bash scripts/load-test.sh \
  --env prod \
  --users 5 \
  --spawn-rate 1 \
  --duration 2m \
  --jwt "<your-token>"
```

### Standard baseline test (20 users, 5 minutes)

```bash
bash scripts/load-test.sh \
  --env prod \
  --users 20 \
  --spawn-rate 2 \
  --duration 5m \
  --jwt "<your-token>"
```

### Stress test (50 users, 10 minutes)

```bash
bash scripts/load-test.sh \
  --env prod \
  --users 50 \
  --spawn-rate 5 \
  --duration 10m \
  --jwt "<your-token>"
```

Results are saved to `.load-test-results/results-<env>-<timestamp>*.csv` and an HTML report is generated at `.load-test-results/results-<env>-<timestamp>.html`.

---

## Performance Baselines

Run the standard 20-user test and record the results here after each major release. These numbers inform when to tighten or loosen CloudWatch alarm thresholds.

> **First run:** Fill in this table with results from your initial prod deployment.

| Endpoint | p50 (ms) | p95 (ms) | p99 (ms) | Threshold to alarm at |
|---|---|---|---|---|
| GET /identities | — | — | — | p99 > 5000 ms |
| GET /scores | — | — | — | p99 > 5000 ms |
| GET /incidents | — | — | — | p99 > 5000 ms |
| GET /events | — | — | — | p99 > 8000 ms |
| GET /trust-relationships | — | — | — | p99 > 5000 ms |
| GET /remediation/config | — | — | — | p99 > 3000 ms |
| GET /remediation/audit | — | — | — | p99 > 5000 ms |

---

## Updating CloudWatch Alarm Thresholds

The `lambda_duration` alarm in `infra/modules/cloudwatch/alarms.tf` uses a hardcoded 24 000 ms threshold (80% of a 30s timeout). After establishing baselines, update this to a data-driven value:

```hcl
# infra/modules/cloudwatch/alarms.tf — lambda_duration alarm
threshold = <p99_from_load_test * 1.5>   # 50% headroom above observed p99
```

Then redeploy:
```bash
bash scripts/deploy-infra.sh --env prod --auto-approve
```

---

## Interpreting Results

### What to look for in the Locust HTML report

| Metric | Good | Investigate |
|---|---|---|
| Failure rate | 0% | > 0.1% |
| p99 latency | < 3000 ms | > 5000 ms |
| RPS (requests/sec) | Stable | Drops mid-test (throttling) |
| Response time chart | Flat | Sawtooth (cold-start spikes) |

### What to watch in CloudWatch during the test

Open the Radius CloudWatch dashboard while the test runs:

```bash
# Get the dashboard URL
aws cloudwatch get-dashboard \
  --dashboard-name "radius-prod-main" \
  --query 'DashboardBody' \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print('Open CloudWatch dashboard: radius-prod-main')"
```

Key metrics to observe:
- **Lambda Duration (p99)** — compare against the current alarm threshold
- **Lambda Throttles** — should be 0 at 20 users; if > 0, consider increasing `lambda_concurrency_limit`
- **API Gateway Latency** — includes Lambda cold-starts; first few requests will be higher
- **DynamoDB ConsumedReadCapacityUnits** — verify on-demand scaling is absorbing the load

### Cold-start behavior with VPC

When `enable_vpc = true`, Lambda cold-starts are 2–4x slower than without VPC. The first request of each new concurrent execution will have elevated latency. This is normal and should not trigger alarms after the pool warms up. If cold-start spikes are frequent, consider provisioned concurrency for `api_handler`:

```hcl
# infra/modules/lambda/main.tf — api_handler resource
provisioned_concurrent_executions = 2  # keeps 2 warm instances
```

---

## Storing Results

Commit the `.load-test-results/*.html` reports to the wiki or an S3 bucket after each test:

```bash
# Upload to the Terraform state bucket
aws s3 cp .load-test-results/ \
  "s3://<your-tf-state-bucket>/load-test-results/$(date +%Y%m%d)/" \
  --recursive \
  --region us-east-1
```

Do **not** commit result files to the git repository — they can be large and contain environment-specific data.
