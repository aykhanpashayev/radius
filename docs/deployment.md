# Deployment Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [First-Time Setup](#first-time-setup)
- [Deploying](#deploying)
- [Injecting Sample Events (Dev Only)](#injecting-sample-events-dev-only)
- [Phase 7 Resources](#phase-7-resources)
- [Dev vs Prod Differences](#dev-vs-prod-differences)
- [Rollback](#rollback)
- [Troubleshooting](#troubleshooting)

## Prerequisites

| Tool | Minimum Version | Notes |
|---|---|---|
| AWS CLI | 2.x | Configured with credentials for the target account |
| Terraform | 1.5.0 | `terraform -version` to verify |
| Python | 3.11+ | Used for Lambda packaging and utility scripts |
| pip | 23.x | Bundled with Python 3.11 |
| zip | any | Standard system utility for Lambda packaging |

### Required IAM Permissions

The deploying principal needs the following AWS managed policies (or equivalent custom policy):

- `AdministratorAccess` — recommended for first-time setup
- Minimum: IAM, Lambda, DynamoDB, S3, SNS, EventBridge, API Gateway, CloudTrail, CloudWatch, KMS create/update/delete permissions

### Pre-deployment Checklist

- [ ] AWS CLI configured: `aws sts get-caller-identity` returns your account ID
- [ ] S3 bucket for Terraform state created (see Step 1 below)
- [ ] S3 bucket for Lambda packages available (can be the same bucket)
- [ ] `lambda_s3_bucket` set in `infra/envs/dev/terraform.tfvars`

---

## First-Time Setup

### Step 1 — Create the Terraform state bucket

```bash
aws s3 mb s3://radius-terraform-state-dev --region us-east-1

aws s3api put-bucket-versioning \
  --bucket radius-terraform-state-dev \
  --versioning-configuration Status=Enabled
```

Versioning is required for the rollback procedure described below.

### Step 2 — Configure the Terraform backend

Create `infra/envs/dev/backend.tfvars`:

```hcl
bucket         = "radius-terraform-state-dev"
key            = "radius/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "radius-terraform-locks"
```

> The `dynamodb_table` lock table is created automatically by Terraform on first `init` if it does not exist.

### Step 3 — Configure variables

Edit `infra/envs/dev/terraform.tfvars`. The only value you must set before deploying is `lambda_s3_bucket`:

```hcl
# infra/envs/dev/terraform.tfvars (excerpt)
environment     = "dev"
aws_region      = "us-east-1"
resource_prefix = "radius-dev"

lambda_s3_bucket = "my-artifact-bucket"   # <-- set this

lambda_memory = {
  event_normalizer   = 512
  detection_engine   = 1024
  incident_processor = 512
  identity_collector = 512
  score_engine       = 1024
  api_handler        = 256
}

lambda_timeout = {
  event_normalizer   = 30
  detection_engine   = 60
  incident_processor = 30
  identity_collector = 30
  score_engine       = 60
  api_handler        = 10
}

lambda_concurrency_limit        = 10
log_retention_days              = 7
cloudtrail_organization_enabled = false
enable_pitr                     = false
score_engine_schedule           = "rate(24 hours)"
```

---

## Deploying

### Step 1 — Build Lambda packages

```bash
./scripts/build-lambdas.sh --env dev --bucket my-artifact-bucket --region us-east-1
```

What it does:
- Installs Python dependencies for each of the 6 functions into a build directory
- Copies `backend/common/` shared utilities into each package
- Zips each package (excluding `*.pyc` and `__pycache__`)
- Uploads to `s3://<bucket>/functions/<function_name>.zip`

If `lambda_s3_bucket` is set in `terraform.tfvars`, you can omit `--bucket`:

```bash
./scripts/build-lambdas.sh --env dev
```

### Step 2 — Deploy infrastructure

```bash
./scripts/deploy-infra.sh --env dev
```

This runs `terraform init -backend-config=backend.tfvars`, `terraform plan`, prompts for approval, then applies.

**Plan only (no changes applied):**
```bash
./scripts/deploy-infra.sh --env dev --plan-only
```

**Auto-approve (CI/CD pipelines):**
```bash
./scripts/deploy-infra.sh --env dev --auto-approve
```

### Step 3 — Verify deployment

```bash
./scripts/verify-deployment.sh --env dev --region us-east-1
```

Checks:
- All 6 Lambda functions are in `Active` state
- All 5 DynamoDB tables are in `ACTIVE` status
- API Gateway endpoint returns HTTP 200
- CloudTrail trail is in `IsLogging: true` state
- SNS topic exists and has at least one subscription (if configured)

---

## Injecting Sample Events (Dev Only)

```bash
# Inject all sample events from the sample-data directory
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events

# Inject a single event file
python scripts/inject-events.py --env dev --file sample-data/cloud-trail-events/sts-assume-role.json

# Dry run — validate events without sending to EventBridge
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events --dry-run
```

---

## Phase 7 Resources

Phase 7 added the Remediation_Engine and its supporting infrastructure. The resources below are in addition to the six Lambda functions and five DynamoDB tables deployed in earlier phases.

### New Lambda Function

| Function name | Handler | Description |
|---|---|---|
| `{env}-remediation-engine` | `handler.lambda_handler` | Evaluates remediation rules and executes approved IAM mutations against offending identities |

### New DynamoDB Tables

| Table name | Description |
|---|---|
| `{env}-remediation-config` | Singleton config record (`config_id=global`) storing risk mode, rules, exclusions, and allowed IP ranges |
| `{env}-remediation-audit-log` | Append-only audit log of every action evaluation — executed, skipped, suppressed, or failed |

### New SNS Topic

| Topic name | Description |
|---|---|
| `{env}-radius-remediation` | Receives structured JSON notifications when risk mode is `alert` or `enforce` |

### New Environment Variables

**`{env}-incident-processor`** — added in Phase 7:

| Variable | Value | Description |
|---|---|---|
| `REMEDIATION_LAMBDA_ARN` | `arn:aws:lambda:{region}:{account}:function:{env}-remediation-engine` | ARN of the Remediation_Engine Lambda; Incident_Processor invokes it asynchronously for every new incident |

**`{env}-api-handler`** — added in Phase 7:

| Variable | Value | Description |
|---|---|---|
| `REMEDIATION_CONFIG_TABLE` | `{env}-remediation-config` | DynamoDB table for remediation config reads/writes |
| `REMEDIATION_AUDIT_TABLE` | `{env}-remediation-audit-log` | DynamoDB table for audit log queries |

### IAM Permissions — `{env}-remediation-engine` Role

The Remediation_Engine Lambda role requires the following permissions in addition to the standard Lambda execution role:

| Permission | Resource | Purpose |
|---|---|---|
| `dynamodb:GetItem` | `{env}-remediation-config` | Load global config |
| `dynamodb:UpdateItem` | `{env}-remediation-config` | Update risk mode |
| `dynamodb:PutItem` | `{env}-remediation-audit-log` | Write audit entries |
| `dynamodb:Query` | `{env}-remediation-audit-log` | Safety control cooldown/rate-limit checks |
| `sns:Publish` | `{env}-radius-remediation` | Publish remediation notifications |
| `iam:ListAccessKeys` | `*` | `disable_iam_user` action |
| `iam:UpdateAccessKey` | `*` | `disable_iam_user` action |
| `iam:DeleteLoginProfile` | `*` | `disable_iam_user` action |
| `iam:ListAttachedUserPolicies` | `*` | `remove_risky_policies` action |
| `iam:ListAttachedRolePolicies` | `*` | `remove_risky_policies` action |
| `iam:ListUserPolicies` | `*` | `remove_risky_policies` action |
| `iam:ListRolePolicies` | `*` | `remove_risky_policies` action |
| `iam:GetUserPolicy` | `*` | `remove_risky_policies` action |
| `iam:GetRolePolicy` | `*` | `remove_risky_policies` action |
| `iam:DetachUserPolicy` | `*` | `remove_risky_policies` action |
| `iam:DetachRolePolicy` | `*` | `remove_risky_policies` action |
| `iam:DeleteUserPolicy` | `*` | `remove_risky_policies` action |
| `iam:DeleteRolePolicy` | `*` | `remove_risky_policies` action |
| `iam:GetRole` | `*` | `block_role_assumption` action |
| `iam:UpdateAssumeRolePolicy` | `*` | `block_role_assumption` action |
| `iam:PutUserPolicy` | `*` | `restrict_network_access` action |
| `iam:PutRolePolicy` | `*` | `restrict_network_access` action |

> **Note:** In production, scope `iam:*` permissions to specific resource ARNs or use permission boundaries to limit the blast radius of the Remediation_Engine role itself.

---

## Dev vs Prod Differences

| Setting | Dev | Prod |
|---|---|---|
| `resource_prefix` | `radius-dev` | `radius-prod` |
| `cloudtrail_organization_enabled` | `false` | `true` (requires Org management account) |
| `enable_pitr` | `false` | `true` (all tables) |
| `log_retention_days` | `7` | `30` |
| `lambda_concurrency_limit` | `10` | not set (unreserved) |
| `lambda_memory.detection_engine` | `1024 MB` | `2048 MB` |
| `lambda_memory.score_engine` | `1024 MB` | `2048 MB` |
| CloudWatch alarm thresholds | relaxed | strict |
| SNS subscriptions | optional | required (ops team email) |

---

## Rollback

Terraform state is versioned in S3. To roll back to a previous deployment:

```bash
# 1. List available state versions
aws s3api list-object-versions \
  --bucket radius-terraform-state-dev \
  --prefix radius/dev/terraform.tfstate \
  --query 'Versions[*].{VersionId:VersionId,LastModified:LastModified}' \
  --output table

# 2. Restore the desired version
aws s3api copy-object \
  --bucket radius-terraform-state-dev \
  --copy-source "radius-terraform-state-dev/radius/dev/terraform.tfstate?versionId=<VERSION_ID>" \
  --key radius/dev/terraform.tfstate

# 3. Re-apply to reconcile infrastructure with the restored state
./scripts/deploy-infra.sh --env dev --auto-approve
```

---

## Troubleshooting

### Lambda function not updating after a code change

**Symptom:** Deploying after a code change has no effect — the old function code is still running.

**Cause:** Terraform detects Lambda package changes via the S3 object ETag. If `build-lambdas.sh` was not re-run, the ETag is unchanged and Terraform skips the update.

**Resolution:**
```bash
./scripts/build-lambdas.sh --env dev
./scripts/deploy-infra.sh --env dev
```

---

### Lambda timeout on large CloudTrail event batches

**Symptom:** Event_Normalizer or Detection_Engine invocations fail with `Task timed out after X seconds`.

**Cause:** Default timeouts (30s / 60s) are too short for large event payloads or slow DynamoDB responses under load.

**Resolution:** Increase the timeout in `terraform.tfvars` and redeploy:

```hcl
lambda_timeout = {
  event_normalizer = 60   # was 30
  detection_engine = 120  # was 60
  ...
}
```

Then run `./scripts/deploy-infra.sh --env dev`.

---

### DynamoDB throttling errors in CloudWatch

**Symptom:** CloudWatch alarms fire for `SystemErrors` or `ThrottledRequests` on DynamoDB tables.

**Cause:** On-demand billing mode handles bursts automatically, but very sudden spikes (e.g. bulk event injection) can trigger transient throttling before DynamoDB scales.

**Resolution:**
- For dev: reduce injection rate in `scripts/inject-events.py` using `--delay` flag
- For prod: review CloudWatch metrics to confirm the spike is transient; if sustained, consider switching high-traffic tables to provisioned capacity with auto-scaling
- The `dynamodb_utils.py` retry logic handles transient throttling with exponential backoff (3 retries, 100ms base delay)

---

### EventBridge rule not routing CloudTrail events to Event_Normalizer

**Symptom:** CloudTrail events are being recorded but Event_Normalizer is never invoked.

**Cause:** Common causes are (1) the EventBridge rule event pattern does not match the event source/type, (2) the Lambda resource-based policy is missing the EventBridge principal, or (3) the CloudTrail trail is not delivering to CloudWatch Logs / EventBridge.

**Resolution:**
1. Verify the trail is logging: `aws cloudtrail get-trail-status --name <trail-name>`
2. Check the EventBridge rule is enabled: `aws events describe-rule --name <rule-name>`
3. Test the rule pattern manually in the EventBridge console using a sample CloudTrail event
4. Verify Lambda permissions: `aws lambda get-policy --function-name <event-normalizer-name>` — should include a statement allowing `events.amazonaws.com` to invoke

---

### Terraform state lock not released after interrupted apply

**Symptom:** `terraform apply` fails with `Error acquiring the state lock`.

**Resolution:**
```bash
# Get the lock ID from the error message, then:
terraform -chdir=infra/envs/dev force-unlock <LOCK_ID>
```
