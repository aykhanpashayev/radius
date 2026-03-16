# Deployment Guide

## Prerequisites

- AWS CLI configured with credentials for the target account
- Terraform >= 1.5.0
- Python 3.11
- `pip`, `zip` (for Lambda packaging)
- An S3 bucket for Terraform state (create manually before first deploy)
- An S3 bucket for Lambda deployment packages (can be the same bucket)

## First-Time Setup

### 1. Create state and artifact buckets

```bash
aws s3 mb s3://radius-terraform-state-dev --region us-east-1
aws s3api put-bucket-versioning \
  --bucket radius-terraform-state-dev \
  --versioning-configuration Status=Enabled
```

### 2. Configure backend

Edit `infra/envs/dev/backend.tfvars`:
```hcl
bucket         = "radius-terraform-state-dev"
key            = "radius/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "radius-terraform-locks"
```

### 3. Configure variables

Edit `infra/envs/dev/terraform.tfvars` and set `lambda_s3_bucket` to your artifact bucket name.

## Deploying

### Step 1 — Build Lambda packages

```bash
./scripts/build-lambdas.sh --env dev --bucket my-artifact-bucket --region us-east-1
```

This installs dependencies, zips each function, and uploads to `s3://my-artifact-bucket/functions/<name>.zip`.

### Step 2 — Deploy infrastructure

```bash
./scripts/deploy-infra.sh --env dev
```

This runs `terraform init`, `terraform plan`, prompts for approval, then applies. Use `--auto-approve` to skip the prompt in CI.

To preview without applying:
```bash
./scripts/deploy-infra.sh --env dev --plan-only
```

### Step 3 — Verify deployment

```bash
./scripts/verify-deployment.sh --env dev --region us-east-1
```

Checks Lambda function states, DynamoDB table status, API Gateway endpoint health, and CloudTrail logging status.

## Seeding Test Data (Dev Only)

```bash
python scripts/seed-dev-data.py --env dev --region us-east-1
```

Populates Identity_Profile, Blast_Radius_Score, Incident, and Trust_Relationship tables with sample records.

## Injecting Sample Events (Dev Only)

```bash
# Inject all sample events
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events

# Inject a single event
python scripts/inject-events.py --env dev --file sample-data/cloud-trail-events/sts-assume-role.json

# Dry run (validate without sending)
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events --dry-run
```

## Prod Deployment

Same steps as dev, using `--env prod`. Key differences:
- `cloudtrail_organization_enabled = true` — requires AWS Organizations management account credentials
- `enable_pitr = true` — point-in-time recovery enabled on all tables
- `log_retention_days = 30`
- No `lambda_concurrency_limit` (unreserved)

## Rollback

To roll back to a previous Terraform state:

```bash
# List state versions in S3
aws s3api list-object-versions --bucket radius-terraform-state-dev \
  --prefix radius/dev/terraform.tfstate

# Restore a previous version
aws s3api copy-object \
  --bucket radius-terraform-state-dev \
  --copy-source "radius-terraform-state-dev/radius/dev/terraform.tfstate?versionId=<VERSION_ID>" \
  --key radius/dev/terraform.tfstate
```

Then re-run `deploy-infra.sh` to reconcile infrastructure with the restored state.

## Troubleshooting

**Lambda not updating after code change:** Re-run `build-lambdas.sh` then `deploy-infra.sh`. Terraform detects S3 object changes via ETag.

**Terraform state lock:** If a previous apply was interrupted, release the lock:
```bash
terraform -chdir=infra/envs/dev force-unlock <LOCK_ID>
```

**CloudTrail not delivering events:** Verify the S3 bucket policy allows CloudTrail write access and the trail is in `IsLogging: true` state.
