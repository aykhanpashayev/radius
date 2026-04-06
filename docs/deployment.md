# Deployment Guide

## Table of Contents

- [What Gets Deployed](#what-gets-deployed)
- [Supported Environments](#supported-environments)
- [Prerequisites](#prerequisites)
  - [1. Python 3.11 or higher](#1-python-311-or-higher)
  - [2. pip](#2-pip)
  - [3. Terraform 1.5.0 or higher](#3-terraform-150-or-higher)
  - [4. AWS CLI v2](#4-aws-cli-v2)
  - [5. Configure AWS credentials](#5-configure-aws-credentials)
  - [6. jq (optional)](#6-jq-optional)
  - [7. git](#7-git)
- [Quick Start — Local Testing (No AWS Required)](#quick-start--local-testing-no-aws-required)
- [Full AWS Deployment](#full-aws-deployment)
  - [Step 1 — Run the preflight check](#step-1--run-the-preflight-check)
  - [Step 2 — Create the S3 buckets](#step-2--create-the-s3-buckets)
  - [Step 3 — Fill in the config files](#step-3--fill-in-the-config-files)
  - [Step 4 — Install Python dependencies](#step-4--install-python-dependencies)
  - [Step 5 — Run the test suite](#step-5--run-the-test-suite)
  - [Step 6 — Build Lambda packages](#step-6--build-lambda-packages)
  - [Step 7 — Deploy infrastructure](#step-7--deploy-infrastructure)
  - [Step 8 — Verify the deployment](#step-8--verify-the-deployment)
  - [Step 9 — Seed test data (optional)](#step-9--seed-test-data-optional)
- [Post-Deployment Validation](#post-deployment-validation)
- [Testing the Remediation Engine](#testing-the-remediation-engine)
- [Viewing the Dashboard and Monitoring](#viewing-the-dashboard-and-monitoring)
  - [React Dashboard](#react-dashboard)
  - [Adding More Users](#adding-more-users)
  - [CloudWatch Dashboards](#cloudwatch-dashboards)
  - [CloudWatch Logs](#cloudwatch-logs-lambda-execution-logs)
  - [DynamoDB Tables](#dynamodb-tables-raw-data)
- [Dev vs Prod Differences](#dev-vs-prod-differences)
- [Rollback](#rollback)
- [Cleanup — Destroy All Resources](#cleanup--destroy-all-resources)
- [Troubleshooting](#troubleshooting)
- [Windows Users](#windows-users)
- [Known Limitations](#known-limitations)

---

## What Gets Deployed

Running the full deployment creates the following AWS resources in your account:

| Resource | Count | Description |
|---|---|---|
| Lambda functions | 7 | Event_Normalizer, Detection_Engine, Incident_Processor, Identity_Collector, Score_Engine, API_Handler, Remediation_Engine |
| DynamoDB tables | 7 | Identity_Profile, Blast_Radius_Score, Incident, Event_Summary, Trust_Relationship, Remediation_Config, Remediation_Audit_Log |
| SNS topics | 2 | Alert_Topic (high-severity incidents), Remediation_Topic (remediation notifications) |
| API Gateway | 1 | REST API serving the React dashboard |
| EventBridge rules | 2 | CloudTrail event routing, Score_Engine schedule |
| CloudTrail trail | 1 | Management event capture (single-account in dev) |
| KMS keys | 4 | Encryption for DynamoDB, SNS, Lambda, CloudTrail |
| CloudWatch | Alarms + log groups | One log group per Lambda, alarms for errors and throttles |
| S3 bucket | 1 | CloudTrail log storage (created by Terraform) |

**Estimated cost in dev:** Under $5/month at low event volume. The main cost drivers are KMS key fees ($1/key/month) and Lambda invocations. DynamoDB uses on-demand billing and costs nothing at zero traffic.

---

## Supported Environments

| Environment | Status | Notes |
|---|---|---|
| Linux (Ubuntu, Debian, Amazon Linux) | Fully supported | All scripts work natively |
| macOS | Fully supported | All scripts work natively |
| Windows with WSL2 | Supported | Run all `.sh` scripts inside WSL2 |
| Windows with Git Bash | Mostly supported | Shell scripts work; some edge cases with paths |
| Windows PowerShell only | Partial | Python scripts and `terraform` work; `.sh` scripts require WSL2 or Git Bash |
| GitHub Codespaces / Gitpod | Fully supported | Linux environment, all scripts work |

**Windows recommendation:** Install WSL2 (Windows Subsystem for Linux). Once WSL2 is set up, open a WSL2 terminal and follow the Linux instructions. See [Windows Users](#windows-users) for setup steps.

---

## Prerequisites

Install all of the following tools **before** cloning the repo or running any commands. The preflight script will verify each one is present and at the right version.

### 1. Python 3.11 or higher

Python runs the backend tests, the demo script, and the Lambda build tooling.

**Linux (Ubuntu/Debian):**
```bash
sudo apt update && sudo apt install -y python3.11 python3-pip python3.11-venv
```

**macOS:**
```bash
brew install python@3.11
```

**Windows:** Download the installer from https://python.org/downloads — tick "Add Python to PATH" during installation.

Verify: `python --version` should print `3.11.x` or higher.

---

### 2. pip

pip is included with Python 3.11. Verify it works:
```bash
pip --version
```

If it's missing: `python -m ensurepip --upgrade`

---

### 3. Terraform 1.5.0 or higher

Terraform provisions all AWS infrastructure.

**Linux:**
```bash
sudo apt install -y gnupg software-properties-common curl
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt update
sudo apt install -y terraform
```

**macOS:**
```bash
brew tap hashicorp/tap && brew install hashicorp/tap/terraform
```

**Windows:** Download the zip from https://developer.hashicorp.com/terraform/downloads, extract `terraform.exe`, and add it to your PATH. Or use `winget install HashiCorp.Terraform`.

Verify: `terraform version` should print `Terraform v1.5.x` or higher.

---

### 4. AWS CLI v2

The AWS CLI is used to create S3 buckets, verify deployments, and interact with AWS services.

**Linux:**
```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip && sudo ./aws/install
```

**macOS:**
```bash
brew install awscli
```

**Windows:** Download and run the MSI installer from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html. Or use `winget install Amazon.AWSCLI`.

Verify: `aws --version` should print `aws-cli/2.x.x`.

---

### 5. Configure AWS credentials

After installing the AWS CLI, configure it with your credentials:

```bash
aws configure
```

You will be prompted for:
- **AWS Access Key ID** — from your IAM user or SSO session
- **AWS Secret Access Key** — from your IAM user or SSO session
- **Default region** — enter `us-east-1` (or your preferred region)
- **Default output format** — enter `json`

Verify credentials work:
```bash
aws sts get-caller-identity
```

Expected output (values will differ):
```json
{
    "UserId": "AIDAEXAMPLEID",
    "Account": "123456789012",
    "Arn": "arn:aws:iam::123456789012:user/your-username"
}
```

If this fails, your credentials are wrong or expired. Re-run `aws configure`.

**Required IAM permissions:** Your AWS user or role needs the following managed policies (or equivalent):
- `AdministratorAccess` — simplest for a first deployment
- Minimum custom policy: IAM, Lambda, DynamoDB, S3, SNS, EventBridge, API Gateway, CloudTrail, CloudWatch, KMS, SQS create/update/delete

### 6. jq (optional)

`jq` is not required but is useful for inspecting JSON output from AWS CLI commands.

**Linux:** `sudo apt install jq`
**macOS:** `brew install jq`
**Windows:** `winget install jqlang.jq`

---

### 7. git

To clone the repository.

**Linux:** `sudo apt install git`
**macOS:** `brew install git` or install Xcode Command Line Tools: `xcode-select --install`
**Windows:** Download from https://git-scm.com/download/win — this also installs Git Bash.

---

### Quick prerequisite check

Once everything is installed, run the preflight script to confirm all tools are ready before proceeding:

```bash
# Linux/macOS/WSL2:
bash scripts/preflight.sh --env dev --skip-aws

# Windows (PowerShell):
.\scripts\preflight.ps1 -Env dev -SkipAws
```

All items should show `[PASS]`. Fix any `[FAIL]` items before continuing.

---

## Quick Start — Local Testing (No AWS Required)

You can run the full test suite and the attack simulation demo without any AWS account or credentials. This is the fastest way to verify the project works.

```bash
# 1. Clone the repo
git clone <repo-url>
cd radius

# 2. Create a virtual environment (keeps dependencies isolated)
python -m venv .venv

# 3. Activate it
#    Linux/macOS:
source .venv/bin/activate
#    Windows (PowerShell):
.venv\Scripts\Activate.ps1
#    Windows (Git Bash / WSL2):
source .venv/Scripts/activate

# 4. Install all test dependencies
pip install -r backend/requirements-dev.txt

# 5. Run the full test suite (no AWS credentials needed — uses moto mock)
bash scripts/run-tests.sh

# 6. Run the attack simulation demo (no AWS credentials needed)
python scripts/simulate-attack.py --mode mock
```

**Expected output from step 5:** All tests pass with a suite summary table. You should see something like:
```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Suite                     Tests    Passed   Failed   Coverage   Duration
─────────────────────────────────────────────────────────────────────────────
Unit Tests                180      180      0        87%        8.2s
Integration Tests         90       90       0        91%        14.1s
Property-Based Tests      36       36       0        N/A        22.4s
─────────────────────────────────────────────────────────────────────────────
TOTAL                     306      306      0                   44.7s
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
All tests passed.
```

**Expected output from step 6:** A five-phase attack simulation showing identity seeding, event injection, incident detection, blast radius scoring, and audit log entries — all running against an in-memory mock AWS environment.

---

## Production — Org-Wide CloudTrail Prerequisites

Enabling `cloudtrail_organization_enabled = true` in `infra/envs/prod/terraform.tfvars` requires additional AWS Organizations setup that must be completed manually before running Terraform. These steps cannot be automated.

### Requirement 1: Management account or delegated admin

The AWS account running Terraform must be either:
- The Organizations **management account**, OR
- A **delegated administrator** for CloudTrail (recommended for prod)

To designate a delegated admin from the management account:
```bash
aws organizations register-delegated-administrator \
  --account-id YOUR_SECURITY_ACCOUNT_ID \
  --service-principal cloudtrail.amazonaws.com
```

### Requirement 2: Enable trusted access for CloudTrail

From the management account:
```bash
aws organizations enable-aws-service-access \
  --service-principal cloudtrail.amazonaws.com
```

Verify it's enabled:
```bash
aws organizations list-aws-service-access-for-organization \
  --query "EnabledServicePrincipals[?ServicePrincipal=='cloudtrail.amazonaws.com']"
```

### Requirement 3: S3 bucket policy for org trail

The S3 bucket receiving CloudTrail logs needs a policy that allows all accounts in the org to write to it. Terraform handles this automatically via the `cloudtrail` module — but the bucket must be in the management account or delegated admin account, not a member account.

Verify your `terraform.tfvars` has the correct account context:
```hcl
cloudtrail_organization_enabled = true
# The account running Terraform must be mgmt or delegated admin
```

### What happens if you skip these steps

Terraform apply will succeed but the CloudTrail trail will silently fail to capture events from member accounts. You will see events only from the account that created the trail. There is no error — it simply doesn't work.

---

## Full AWS Deployment

Follow these steps in order. Each step explains what you're doing and what success looks like.

### Step 1 — Run the preflight check

The preflight script checks that all required tools are installed, your AWS credentials work, and your config files are ready. Run it before anything else.

```bash
# Linux/macOS/WSL2:
bash scripts/preflight.sh --env dev

# Windows (PowerShell):
.\scripts\preflight.ps1 -Env dev
```

**What to expect:** A list of PASS/WARN/FAIL items. Fix every `[FAIL]` before continuing. `[WARN]` items are advisory.

**If AWS credentials fail:** Run `aws configure` and enter your Access Key ID, Secret Access Key, region (`us-east-1`), and output format (`json`). Then re-run the preflight.

---

### Step 2 — Create the S3 buckets

Terraform needs an S3 bucket to store its state file. Lambda packages also need an S3 bucket. You can use the same bucket for both, or separate ones.

> **Note:** Replace `YOUR-STATE-BUCKET` in all commands below with your own globally unique bucket name.

```bash
# Replace "YOUR-STATE-BUCKET" with a globally unique bucket name (S3 names are global)
aws s3 mb s3://YOUR-STATE-BUCKET --region us-east-1

# Enable versioning so you can roll back Terraform state if needed
aws s3api put-bucket-versioning \
  --bucket YOUR-STATE-BUCKET \
  --versioning-configuration Status=Enabled
```

**Why versioning?** If a Terraform apply goes wrong, you can restore a previous state file from S3 version history. See [Rollback](#rollback).

**Verify it worked:**
```bash
aws s3 ls s3://YOUR-STATE-BUCKET
# Should return an empty listing (no error)
```

---

### Step 3 — Fill in the config files

Two config files need your values before deployment can proceed. Both were created with placeholder values when you cloned the repo.

**File 1: `infra/envs/dev/backend.tfvars`**

Open this file and replace the placeholder with your state bucket name:

```hcl
bucket         = "YOUR-STATE-BUCKET"   # <-- your bucket name from Step 2
key            = "radius/dev/terraform.tfstate"
region         = "us-east-1"
dynamodb_table = "radius-terraform-locks"
encrypt        = true
```

**File 2: `infra/envs/dev/terraform.tfvars`**

Open this file and set `lambda_s3_bucket` to the bucket where Lambda packages will be uploaded. This can be the same bucket as the state bucket:

```hcl
lambda_s3_bucket = "YOUR-STATE-BUCKET"   # <-- your bucket name
```

Everything else in `terraform.tfvars` has sensible defaults for dev. You don't need to change anything else.

**Verify:** Re-run the preflight check — the config file checks should now show `[PASS]`.

---

### Step 4 — Install Python dependencies

```bash
pip install -r backend/requirements-dev.txt
```

This installs pytest, moto, hypothesis, boto3, and all other packages needed to run tests and scripts.

**Verify:**
```bash
python -c "import boto3, moto, pytest, hypothesis; print('OK')"
# Should print: OK
```

---

### Step 5 — Run the test suite

Always run tests before building and deploying. This confirms the backend logic is correct before you spend time on infrastructure.

```bash
# Full suite (unit + integration + property-based) with coverage summary:
bash scripts/run-tests.sh

# Fast mode (skip property-based tests, ~15 seconds):
bash scripts/run-tests.sh --fast
```

**Expected output:** All tests pass with a suite summary table. If any fail, do not proceed to deployment — fix the failures first.

---

### Step 6 — Build Lambda packages

This step packages each Lambda function's code and dependencies into a zip file and uploads it to S3.

```bash
bash scripts/build-lambdas.sh --env dev --region us-east-1
```

The script reads `lambda_s3_bucket` from `infra/envs/dev/terraform.tfvars` automatically, so you don't need to pass `--bucket` separately.

**What it does:**
1. For each of the 7 Lambda functions, creates a build directory
2. Copies the function code and `backend/common/` shared utilities into it
3. Installs the function's `requirements.txt` dependencies
4. Zips everything up
5. Uploads the zip to `s3://<your-bucket>/functions/<function-name>.zip`

**Verify:**
```bash
aws s3 ls s3://YOUR-STATE-BUCKET/functions/
# Should list 7 zip files: event_normalizer.zip, detection_engine.zip, etc.
```

**If you only want to build locally without uploading to S3:**
```bash
bash scripts/build-lambdas.sh --env dev --local
# Packages are saved to .build/ in the repo root
```

---

### Step 7 — Deploy infrastructure

This runs Terraform to create all AWS resources.

```bash
bash scripts/deploy-infra.sh --env dev
```

**What happens:**
1. `terraform init` — downloads the AWS provider and configures the S3 backend
2. `terraform plan` — shows you exactly what will be created (no changes yet)
3. Prompts you to confirm: type `yes` to apply
4. `terraform apply` — creates all resources (takes 3–8 minutes)
5. Prints key outputs including the API Gateway URL

**To apply without the confirmation prompt (useful for automation):**
```bash
bash scripts/deploy-infra.sh --env dev --auto-approve
```

**To see the plan without applying:**
```bash
bash scripts/deploy-infra.sh --env dev --plan-only
```

**Verify:** Terraform prints `Apply complete!` with a count of resources created. It also prints the `api_endpoint` output — save this URL, you'll need it for the dashboard.

---

### Step 8 — Verify the deployment

After Terraform finishes, run the verification script to confirm all resources are healthy:

```bash
bash scripts/verify-deployment.sh --env dev --region us-east-1
```

**What it checks:**
- All 7 Lambda functions are in `Active` state
- All 7 DynamoDB tables are in `ACTIVE` status
- API Gateway exists and endpoints return expected HTTP codes
- CloudTrail trail exists and is logging

**Expected output:** All checks show `[PASS]`. If any show `[FAIL]`, see [Troubleshooting](#troubleshooting).

---

### Step 9 — Seed test data (optional)

To populate the dashboard with sample identities, scores, and incidents for a demo:

```bash
python scripts/seed-dev-data.py --env dev --region us-east-1
```

To inject sample CloudTrail events and trigger the full detection pipeline:

```bash
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events
```

After injecting events, wait 30–60 seconds for the pipeline to process them, then check the dashboard or query DynamoDB directly to see the results.

---

## Post-Deployment Validation

After deployment, verify the system is actually processing events end-to-end:

```bash
# 1. Inject a single suspicious event
python scripts/inject-events.py --env dev \
  --file sample-data/cloud-trail-events/suspicious-privilege-escalation.json

# 2. Wait 30 seconds for the pipeline to process it

# 3. Check if an incident was created
aws dynamodb scan \
  --table-name radius-dev-incident \
  --region us-east-1 \
  --query "Items[*].{id:incident_id.S, type:detection_type.S, severity:severity.S}" \
  --output table

# 4. Check if a blast radius score was calculated
aws dynamodb scan \
  --table-name radius-dev-blast-radius-score \
  --region us-east-1 \
  --query "Items[*].{arn:identity_arn.S, score:score_value.N, severity:severity_level.S}" \
  --output table
```

If incidents and scores appear, the pipeline is working end-to-end.

---

## Testing the Remediation Engine

The Remediation_Engine evaluates rules against high-severity incidents and optionally executes IAM actions. Follow these steps to confirm it's working.

### Getting a Cognito ID token

Several steps below require a Cognito ID token in the `Authorization` header. Get one with the AWS CLI after creating your user:

Linux/macOS/WSL2:
```bash
aws cognito-idp initiate-auth \
  --auth-flow USER_PASSWORD_AUTH \
  --client-id <your-client-id> \
  --auth-parameters USERNAME=your@email.com,PASSWORD="YourStr0ng!Password" \
  --region us-east-1 \
  --query "AuthenticationResult.IdToken" \
  --output text
```

Windows PowerShell:
```powershell
aws cognito-idp initiate-auth --auth-flow USER_PASSWORD_AUTH --client-id <your-client-id> --auth-parameters USERNAME=your@email.com,PASSWORD="YourStr0ng!Password" --region us-east-1 --query "AuthenticationResult.IdToken" --output text
```

Copy the printed token — it's a long JWT string. Use it as `<your-cognito-id-token>` in the commands below. Tokens expire after 1 hour; re-run the command to get a fresh one.

Get your client ID any time with:
```powershell
terraform -chdir=infra/envs/dev output -raw cognito_client_id
```

### Step 1 — Confirm dry-run mode

By default `remediation_dry_run = true` in dev — the engine evaluates rules and writes audit log entries, but executes no real IAM mutations. Check your `infra/envs/dev/terraform.tfvars`:

```hcl
remediation_dry_run = true   # safe — audit log written, no IAM mutations
```

Verify the deployed Lambda has it set:

Windows PowerShell:
```powershell
aws lambda get-function-configuration --function-name radius-dev-remediation-engine --region us-east-1 --query "Environment.Variables.DRY_RUN" --output text
```

Should print `true`.

### Step 2 — Set risk mode to alert

The engine writes audit entries in **all** modes. However in `monitor` mode, `notify_security_team` is suppressed. Switch to `alert` so the notification action executes:

Windows PowerShell:
```powershell
Invoke-RestMethod -Method PUT -Uri "https://<your-api-endpoint>/remediation/config/mode" -Headers @{ Authorization = "<your-cognito-id-token>"; "Content-Type" = "application/json" } -Body '{"risk_mode":"alert"}'
```

Linux/macOS/WSL2:
```bash
curl -s -X PUT "https://<your-api-endpoint>/remediation/config/mode" \
  -H "Authorization: <your-cognito-id-token>" \
  -H "Content-Type: application/json" \
  -d '{"risk_mode":"alert"}'
```

### Step 3 — Create a remediation rule

Create a rule that fires on Critical incidents and notifies the security team:

Windows PowerShell:
```powershell
Invoke-RestMethod -Method POST -Uri "https://<your-api-endpoint>/remediation/rules" -Headers @{ Authorization = "<your-cognito-id-token>"; "Content-Type" = "application/json" } -Body '{"name":"Test - notify on Critical","min_severity":"Critical","actions":["notify_security_team"],"active":true,"priority":1}'
```

Linux/macOS/WSL2:
```bash
curl -s -X POST "https://<your-api-endpoint>/remediation/rules" \
  -H "Authorization: <your-cognito-id-token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test - notify on Critical","min_severity":"Critical","actions":["notify_security_team"],"active":true,"priority":1}'
```

Get your API endpoint: `terraform -chdir=infra/envs/dev output -raw api_endpoint`

### Step 4 — Trigger a high-severity incident

Invoke Incident_Processor directly with a Critical finding. This creates a new incident and immediately async-invokes the Remediation_Engine.

Windows PowerShell:
```powershell
[System.IO.File]::WriteAllText("$PWD\payload.json", '{"identity_arn":"arn:aws:iam::123456789012:user/test-attacker","detection_type":"privilege_escalation","severity":"Critical","confidence":95,"related_event_ids":["test-001"]}', [System.Text.UTF8Encoding]::new($false))
aws lambda invoke --function-name radius-dev-incident-processor --region us-east-1 --cli-binary-format raw-in-base64-out --payload "fileb://$PWD\payload.json" response.json
Get-Content response.json
```

Linux/macOS/WSL2:
```bash
aws lambda invoke \
  --function-name radius-dev-incident-processor \
  --region us-east-1 \
  --cli-binary-format raw-in-base64-out \
  --payload '{"identity_arn":"arn:aws:iam::123456789012:user/test-attacker","detection_type":"privilege_escalation","severity":"Critical","confidence":95,"related_event_ids":["test-001"]}' \
  response.json && cat response.json
```

Expected: `{"status": "created", "incident_id": "..."}`.

If you see `"deduplicated"` — the same identity+detection_type was already processed within 24 hours. Change `test-attacker` to `test-attacker-2` and retry.

Wait 15–30 seconds for the Remediation_Engine to process it asynchronously.

### Step 5 — Check the remediation audit log

Windows PowerShell:
```powershell
aws dynamodb scan --table-name radius-dev-remediation-audit-log --region us-east-1 --query "Items[*].{action:action_name.S, outcome:outcome.S, mode:risk_mode.S, dry_run:dry_run.BOOL, identity:identity_arn.S}" --output table
```

Linux/macOS/WSL2:
```bash
aws dynamodb scan \
  --table-name radius-dev-remediation-audit-log \
  --region us-east-1 \
  --query "Items[*].{action:action_name.S, outcome:outcome.S, mode:risk_mode.S, dry_run:dry_run.BOOL, identity:identity_arn.S}" \
  --output table
```

**What to look for:**

| action | outcome | dry_run | Meaning |
|---|---|---|---|
| `notify_security_team` | `executed` | `true` | SNS notification sent, no IAM changes (dry-run active) |
| `notify_security_team` | `suppressed` | — | monitor mode or dry_run blocked the action |
| `no_rules_matched` | `skipped` | — | No rules matched — check Step 3 was completed |
| `remediation_suppressed` | `suppressed` | — | Safety control fired (cooldown, excluded ARN) |
| `remediation_complete` | `summary` | — | Final summary record — always written |

A successful test shows `notify_security_team` with `outcome=executed` and a `remediation_complete` summary record.

### Step 6 — Check the remediation config via the API

Windows PowerShell:
```powershell
Invoke-RestMethod -Uri "https://<your-api-endpoint>/remediation/config" -Headers @{ Authorization = "<your-cognito-id-token>" }
```

Linux/macOS/WSL2:
```bash
curl -s "https://<your-api-endpoint>/remediation/config" \
  -H "Authorization: <your-cognito-id-token>"
```

This returns the current `risk_mode`, active rules, and exclusion lists.

### Step 7 — Enable live remediation (prod only)

When you're confident the rules are correct, switch off dry-run in `terraform.tfvars`:

```hcl
remediation_dry_run = false
```

Then redeploy:
```bash
bash scripts/deploy-infra.sh --env prod
```

> **Warning:** With `dry_run = false` and `risk_mode = enforce`, the engine will execute real IAM mutations (detach policies, disable access keys, etc.) on matching identities. Review all rules carefully before enabling.

### Changing the risk mode without redeploying

The risk mode can be changed at runtime via the API without a Terraform redeploy:

Linux/macOS/WSL2:
```bash
curl -s -X PUT \
  "https://<your-api-endpoint>/remediation/config/mode" \
  -H "Authorization: <your-cognito-id-token>" \
  -H "Content-Type: application/json" \
  -d '{"risk_mode": "alert"}'
```

Windows PowerShell:
```powershell
Invoke-RestMethod -Method PUT `
  -Uri "https://<your-api-endpoint>/remediation/config/mode" `
  -Headers @{ Authorization = "<your-cognito-id-token>"; "Content-Type" = "application/json" } `
  -Body '{"risk_mode":"alert"}'
```

Valid values: `monitor` (log only), `alert` (log + SNS notification), `enforce` (log + SNS + IAM actions).

---

## Viewing the Dashboard and Monitoring

### React Dashboard

The React dashboard is the main UI for viewing identities, blast radius scores, incidents, and events. It requires authentication via Cognito — you will be redirected to a login page on first visit.

**Step 1 — Get your deployment outputs**

After `deploy-infra.sh` completes, retrieve the three values you need:

```bash
terraform -chdir=infra/envs/dev output -raw api_endpoint
terraform -chdir=infra/envs/dev output -raw cognito_user_pool_id
terraform -chdir=infra/envs/dev output -raw cognito_client_id
```

**Step 2 — Install Node.js** (if not already installed)

The dashboard is a React/Vite app and requires Node.js 18+.

- Linux: `sudo apt install nodejs npm` or use [nvm](https://github.com/nvm-sh/nvm)
- macOS: `brew install node`
- Windows: Download from https://nodejs.org

Verify: `node --version` should print `v18.x` or higher.

**Step 3 — Configure the frontend environment**

Create `frontend/.env.local` with the values from Step 1.

Linux/macOS/WSL2:
```bash
cat > frontend/.env.local << EOF
VITE_API_BASE_URL=https://<your-api-endpoint>
VITE_COGNITO_USER_POOL_ID=<your-user-pool-id>
VITE_COGNITO_CLIENT_ID=<your-client-id>
EOF
```

Windows PowerShell — use `WriteAllText` to avoid BOM encoding issues:
```powershell
[System.IO.File]::WriteAllText(
  "frontend\.env.local",
  "VITE_API_BASE_URL=https://<your-api-endpoint>`nVITE_COGNITO_USER_POOL_ID=<your-user-pool-id>`nVITE_COGNITO_CLIENT_ID=<your-client-id>`n",
  [System.Text.UTF8Encoding]::new($false)
)
```

> **Windows note:** Do not use PowerShell's `Set-Content` or `Out-File` to create `.env` files — they write UTF-8 with BOM by default, which causes Vite to misread variable names. Use the `WriteAllText` command above, or create the file manually in VS Code.

**Step 4 — Create your first dashboard user**

The Cognito User Pool is admin-only — there is no self-registration. Create a user with the AWS CLI.

Linux/macOS/WSL2:
```bash
aws cognito-idp admin-create-user \
  --user-pool-id <your-user-pool-id> \
  --username your@email.com \
  --region us-east-1

aws cognito-idp admin-set-user-password \
  --user-pool-id <your-user-pool-id> \
  --username your@email.com \
  --password "YourStr0ng!Password" \
  --permanent \
  --region us-east-1
```

Windows PowerShell:
```powershell
aws cognito-idp admin-create-user --user-pool-id <your-user-pool-id> --username your@email.com --region us-east-1

aws cognito-idp admin-set-user-password --user-pool-id <your-user-pool-id> --username your@email.com --password "YourStr0ng!Password" --permanent --region us-east-1
```

Password requirements: minimum 12 characters, uppercase, lowercase, numbers, and symbols.

**Step 5 — Install dependencies and start the dashboard**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — you will be redirected to the login page. Sign in with the email and password you set in Step 4.

**Step 6 — Seed some data so the dashboard has something to show**

```bash
# Seed sample identities, scores, and incidents
python scripts/seed-dev-data.py --env dev --region us-east-1

# Inject sample CloudTrail events to trigger the detection pipeline
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events
```

Wait 30–60 seconds, then refresh the dashboard.

**Adding more users**

To give additional team members access:

Linux/macOS/WSL2:
```bash
aws cognito-idp admin-create-user \
  --user-pool-id <your-user-pool-id> \
  --username colleague@example.com \
  --region us-east-1

aws cognito-idp admin-set-user-password \
  --user-pool-id <your-user-pool-id> \
  --username colleague@example.com \
  --password "TheirStr0ng!Password" \
  --permanent \
  --region us-east-1
```

Windows PowerShell:
```powershell
aws cognito-idp admin-create-user --user-pool-id <your-user-pool-id> --username colleague@example.com --region us-east-1

aws cognito-idp admin-set-user-password --user-pool-id <your-user-pool-id> --username colleague@example.com --password "TheirStr0ng!Password" --permanent --region us-east-1
```

---

### CloudWatch Dashboards

Terraform creates four CloudWatch dashboards for infrastructure monitoring. View them in the AWS Console:

1. Go to **AWS Console → CloudWatch → Dashboards**
2. You will see four dashboards:
   - `radius-dev-lambda` — Lambda invocations, errors, and duration per function
   - `radius-dev-dynamodb` — DynamoDB read/write capacity and throttling per table
   - `radius-dev-api-gateway` — API request count, latency, and error rates
   - `radius-dev-eventbridge` — EventBridge rule invocations and failures

Or open them directly via URL:
```
https://console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards:name=radius-dev-lambda
```

---

### CloudWatch Logs (Lambda execution logs)

Every Lambda function writes structured JSON logs to CloudWatch. To see what's happening in the pipeline:

```bash
# View recent Event_Normalizer logs
aws logs tail /aws/lambda/radius-dev-event-normalizer \
  --region us-east-1 \
  --follow

# View Detection_Engine logs
aws logs tail /aws/lambda/radius-dev-detection-engine \
  --region us-east-1 \
  --follow

# View Incident_Processor logs
aws logs tail /aws/lambda/radius-dev-incident-processor \
  --region us-east-1 \
  --follow
```

Or in the AWS Console: **CloudWatch → Log groups → /aws/lambda/radius-dev-event-normalizer**

---

### DynamoDB Tables (raw data)

View the raw data in any table directly from the AWS Console:

1. Go to **AWS Console → DynamoDB → Tables**
2. Select a table (e.g. `radius-dev-incident`)
3. Click **Explore table items**

Or query via CLI:
```bash
# See all open incidents
aws dynamodb scan \
  --table-name radius-dev-incident \
  --filter-expression "#s = :open" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":open": {"S": "open"}}' \
  --region us-east-1 \
  --output table

# See all blast radius scores
aws dynamodb scan \
  --table-name radius-dev-blast-radius-score \
  --region us-east-1 \
  --output table
```

---

## Dev vs Prod Differences

| Setting | Dev | Prod |
|---|---|---|
| `cloudtrail_organization_enabled` | `false` (single account) | `false` default; set `true` for org-wide coverage (see [Org-Wide CloudTrail Prerequisites](#production--org-wide-cloudtrail-prerequisites)) |
| `enable_pitr` | `true` | `true` (DynamoDB point-in-time recovery) |
| `log_retention_days` | 7 | 365 |
| `lambda_concurrency_limit` | `0` (unreserved) | `0` (unreserved, scales freely) |
| `lambda_memory.detection_engine` | 1024 MB | 2048 MB |
| `score_engine_schedule` | every 24 hours | every 6 hours |
| `remediation_dry_run` | `true` (log only, no IAM mutations) | `false` (live remediation — explicit opt-in) |
| `api_throttle_burst_limit` | 50 | 200 |
| `api_throttle_rate_limit` | 25 rps | 100 rps |
| `cognito_callback_urls` | `http://localhost:5173/callback` | CloudFront domain |
| SNS subscriptions | optional | required (ops team email) |
| Frontend config source | manual `.env.local` | SSM Parameter Store via `build-frontend.sh` |

To deploy to prod, fill in `infra/envs/prod/terraform.tfvars` and `infra/envs/prod/backend.tfvars`, then run the same steps with `--env prod`.

---

## Rollback

Terraform state is versioned in S3. To roll back to a previous deployment:

```bash
# 1. List available state versions
aws s3api list-object-versions \
  --bucket YOUR-STATE-BUCKET \
  --prefix radius/dev/terraform.tfstate \
  --query 'Versions[*].{VersionId:VersionId,LastModified:LastModified}' \
  --output table

# 2. Restore the desired version (replace VERSION_ID with the ID from step 1)
aws s3api copy-object \
  --bucket YOUR-STATE-BUCKET \
  --copy-source "YOUR-STATE-BUCKET/radius/dev/terraform.tfstate?versionId=VERSION_ID" \
  --key radius/dev/terraform.tfstate

# 3. Re-apply to reconcile infrastructure with the restored state
bash scripts/deploy-infra.sh --env dev --auto-approve
```

---

## Cleanup — Destroy All Resources

To remove all AWS resources created by Terraform:

**Linux / macOS / WSL2:**
```bash
cd infra/envs/dev
terraform destroy -var-file=terraform.tfvars
```

**Windows (PowerShell):**
```powershell
Set-Location infra\envs\dev
terraform destroy -var-file=terraform.tfvars
```

Type `yes` when prompted. This takes 3–5 minutes.

> **Windows note:** Do not use `terraform -chdir=infra/envs/dev destroy -var-file=terraform.tfvars` from the repo root on Windows — Terraform misinterprets the bare filename as a plan file and fails with `Failed to load ".tfvars" as a plan file`. Always change into the env directory first.

After destroying, delete the S3 buckets manually if you no longer need them:

**Linux / macOS / WSL2:**
```bash
aws s3 rm s3://YOUR-STATE-BUCKET --recursive
aws s3 rb s3://YOUR-STATE-BUCKET
```

**Windows (PowerShell):**
```powershell
aws s3 rm s3://YOUR-STATE-BUCKET --recursive
aws s3 rb s3://YOUR-STATE-BUCKET
```

---

## Troubleshooting

### "backend/requirements-dev.txt not found"

This file was missing in earlier versions of the repo. It now exists. If you cloned before it was added, pull the latest changes:
```bash
git pull
pip install -r backend/requirements-dev.txt
```

### Tests fail with "ModuleNotFoundError: No module named 'backend'"

This means pytest can't find the `backend` package. Make sure you're running pytest from the **repository root** (the directory containing `pyproject.toml`), not from inside `backend/`:

```bash
# Correct — run from repo root:
python -m pytest backend/tests/ -q

# Wrong — do not cd into backend first
```

The `pyproject.toml` at the repo root sets `pythonpath = ["."]` which fixes this automatically.

### "ERROR: infra/envs/dev/terraform.tfvars still contains placeholder values"

Open `infra/envs/dev/terraform.tfvars` and replace every value that looks like `<REPLACE: ...>` with your actual values. The only required change is `lambda_s3_bucket`.

### Lambda function not updating after a code change

Terraform detects Lambda package changes via the S3 object ETag. If `build-lambdas.sh` was not re-run, the ETag is unchanged and Terraform skips the update.

```bash
bash scripts/build-lambdas.sh --env dev
bash scripts/deploy-infra.sh --env dev
```

### "CloudWatch Logs role ARN must be set in account settings to enable logging"

**Symptom:** Terraform fails with `BadRequestException: CloudWatch Logs role ARN must be set in account settings to enable logging` on the API Gateway stage resource.

**Cause:** API Gateway requires a single IAM role to be configured at the AWS account level before any stage can write access logs to CloudWatch. This is a one-time account setting that was missing.

**Fix:** This is now handled automatically by Terraform — the `aws_api_gateway_account` resource in the `apigateway` module creates the required IAM role and sets it account-wide. Re-run the deploy and it will be created before the stage is configured.

If you hit this on an older checkout, pull the latest changes and re-run:
```bash
bash scripts/deploy-infra.sh --env dev
```

---

### "ResourceConflictException: Function already exists" during terraform apply

**Symptom:** Terraform fails with `ResourceConflictException: Function already exist: radius-dev-<name>` for one or more Lambda functions.

**Cause:** A previous `terraform apply` failed partway through. Some Lambda functions were created in AWS before the error, but Terraform's state file doesn't know about them. On the next apply, Terraform tries to create them again.

**Fix:** Import the existing functions into Terraform state, then re-apply.

```bash
cd infra/envs/dev

# Replace <function-name> with the name from the error, e.g. radius-dev-identity-collector
terraform import -var-file=terraform.tfvars \
  module.radius.module.lambda.aws_lambda_function.<short_name> \
  <function-name>
```

The `<short_name>` mapping is:

| Function name in AWS | short_name for import |
|---|---|
| radius-dev-event-normalizer | event_normalizer |
| radius-dev-detection-engine | detection_engine |
| radius-dev-incident-processor | incident_processor |
| radius-dev-identity-collector | identity_collector |
| radius-dev-score-engine | score_engine |
| radius-dev-api-handler | api_handler |
| radius-dev-remediation-engine | remediation_engine |

Example — importing two functions:
```bash
terraform import -var-file=terraform.tfvars \
  module.radius.module.lambda.aws_lambda_function.identity_collector \
  radius-dev-identity-collector

terraform import -var-file=terraform.tfvars \
  module.radius.module.lambda.aws_lambda_function.remediation_engine \
  radius-dev-remediation-engine
```

After importing all affected functions, re-run:
```bash
bash scripts/deploy-infra.sh --env dev
```

**Alternative — destroy and start fresh:**
If multiple resource types are in a partial state, it may be faster to destroy everything and re-apply:

Linux / macOS / WSL2:
```bash
cd infra/envs/dev
terraform destroy -var-file=terraform.tfvars
cd ../../..
bash scripts/deploy-infra.sh --env dev
```

Windows (PowerShell):
```powershell
Set-Location infra\envs\dev
terraform destroy -var-file=terraform.tfvars
Set-Location ..\..\..
bash scripts/deploy-infra.sh --env dev
```

### "Error acquiring the state lock"

This happens when a previous `terraform apply` was interrupted. Get the lock ID from the error message, then:

```bash
terraform -chdir=infra/envs/dev force-unlock LOCK_ID
```

### Lambda timeout errors in CloudWatch

Increase the timeout in `terraform.tfvars` and redeploy:

```hcl
lambda_timeout = {
  event_normalizer = 60   # was 30
  detection_engine = 120  # was 60
}
```

### EventBridge not routing events to Event_Normalizer

1. Verify the trail is logging: `aws cloudtrail get-trail-status --name radius-dev-trail`
2. Check the EventBridge rule is enabled: `aws events describe-rule --name radius-dev-cloudtrail-rule`
3. Verify Lambda permissions: `aws lambda get-policy --function-name radius-dev-event-normalizer`

### DynamoDB throttling errors

On-demand billing handles bursts automatically, but very sudden spikes can cause transient throttling. For dev, inject events in smaller batches:

```bash
python scripts/inject-events.py --env dev --dir sample-data/cloud-trail-events --dry-run
# Validate first, then inject a single file at a time:
python scripts/inject-events.py --env dev --file sample-data/cloud-trail-events/suspicious-privilege-escalation.json
```

---

## Windows Users

The deployment shell scripts (`build-lambdas.sh`, `deploy-infra.sh`, `verify-deployment.sh`, `preflight.sh`) require a bash environment. On Windows, you have two options:

### Option A — WSL2 (recommended)

WSL2 gives you a full Linux environment inside Windows. It's the most reliable option.

1. Install WSL2: open PowerShell as Administrator and run:
   ```powershell
   wsl --install
   ```
   Restart your computer when prompted.

2. Open the WSL2 terminal (search "Ubuntu" in the Start menu).

3. Install required tools inside WSL2:
   ```bash
   sudo apt update
   sudo apt install -y python3.11 python3-pip
   ```

4. Install Terraform inside WSL2:
   ```bash
   wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
   echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
   sudo apt update && sudo apt install terraform
   ```

5. Install AWS CLI inside WSL2:
   ```bash
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip && sudo ./aws/install
   ```

6. Clone the repo inside WSL2 (not on the Windows filesystem — use `~/radius` not `/mnt/c/...`):
   ```bash
   git clone <repo-url> ~/radius
   cd ~/radius
   ```

7. Follow the [Full AWS Deployment](#full-aws-deployment) steps from inside the WSL2 terminal.

### Option B — Git Bash

Git Bash (included with Git for Windows) can run the shell scripts without WSL2.

1. Install Git for Windows: https://git-scm.com/download/win
2. Open "Git Bash" from the Start menu
3. Follow the Linux deployment steps — they work in Git Bash

### What works natively in PowerShell

These commands work directly in PowerShell without WSL2 or Git Bash:

```powershell
# Run the preflight check
.\scripts\preflight.ps1 -Env dev

# Install Python dependencies
pip install -r backend\requirements-dev.txt

# Run tests
python -m pytest backend\tests\ -q

# Run the demo (no AWS needed)
python scripts\simulate-attack.py --mode mock

# Terraform commands (Terraform has a native Windows binary)
terraform -chdir=infra\envs\dev init -backend-config=backend.tfvars
terraform -chdir=infra\envs\dev plan -var-file=terraform.tfvars
terraform -chdir=infra\envs\dev apply -var-file=terraform.tfvars
```

---

## Known Limitations

**`build-lambdas.sh` on Windows without WSL2:** The script uses bash, which is not available in native PowerShell. Use WSL2 or Git Bash. The script itself uses Python's `zipfile` module for packaging (no `zip` CLI required), so once you have a bash environment it works without any extra tools.

**CloudTrail organization trail:** Setting `cloudtrail_organization_enabled = true` requires deploying from an AWS Organizations management account. This is not available in standalone AWS accounts. Leave it `false` for dev and single-account deployments.

**Terraform state bucket must be created manually:** Terraform cannot create its own state bucket (chicken-and-egg problem). You must create the S3 bucket in Step 2 before running `deploy-infra.sh`.
