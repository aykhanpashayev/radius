# Disaster Recovery Runbook

## Overview

This runbook covers restoring Radius to an operational state after data loss, accidental deletion, or corruption of DynamoDB tables.

**RTO (Recovery Time Objective):** 30 minutes for data restore initiation; 2–20 minutes for DynamoDB table creation; total ≤ 60 minutes from incident declaration to traffic on restored tables.

**RPO (Recovery Point Objective):** ≤ 5 minutes (PITR continuous backup). AWS Backup provides daily snapshots as a secondary fallback.

---

## Backup Coverage

### Tables with PITR (continuous, 35-day window)

| Table | Purpose | Recovery method |
|---|---|---|
| `identity-profile` | IAM identity metadata | PITR or AWS Backup |
| `blast-radius-score` | Current scores per identity | PITR or AWS Backup |
| `incident` | Security incidents | PITR or AWS Backup |
| `remediation-config` | Remediation rules and settings | PITR or AWS Backup |
| `remediation-audit-log` | Append-only remediation history | PITR or AWS Backup |

### Tables WITHOUT PITR (can be rebuilt)

| Table | Why no PITR | Recovery method |
|---|---|---|
| `event-summary` | High-volume, 90-day TTL; old events expire anyway | Replay CloudTrail events through `Event_Normalizer` Lambda |
| `trust-relationship` | Derived data; rebuilt as new CloudTrail events arrive | Allow to rebuild organically over 24–48 hours |

---

## Recovery Procedures

### Option A — PITR Restore (preferred, fastest)

Use this when you need to recover to a specific minute within the last 35 days.

#### Step 1: Declare incident and identify restore target

```bash
# Find the last known-good timestamp (ISO 8601 UTC)
RESTORE_TIME="2026-04-01T10:30:00Z"
ENV="prod"
TABLE="identity-profile"   # one of: identity-profile, blast-radius-score,
                            #         incident, remediation-config, remediation-audit-log
```

#### Step 2: Initiate restore

```bash
bash scripts/restore-dynamodb.sh \
  --table "${TABLE}" \
  --restore-time "${RESTORE_TIME}" \
  --env "${ENV}" \
  --suffix "dr-$(date +%Y%m%d)"
```

The script polls until the restored table is `ACTIVE` (typically 2–20 minutes depending on table size).

#### Step 3: Validate restored data

```bash
RESTORED_TABLE="radius-prod-${TABLE}-dr-$(date +%Y%m%d)"

# Check item count
aws dynamodb describe-table \
  --table-name "${RESTORED_TABLE}" \
  --query 'Table.ItemCount'

# Spot-check a few records
aws dynamodb scan \
  --table-name "${RESTORED_TABLE}" \
  --max-items 5 \
  --output table
```

#### Step 4: Traffic swap

Lambda functions reference table names via environment variables (e.g. `IDENTITY_PROFILE_TABLE`). To swap traffic to the restored table:

```bash
# Option 1 (recommended): Update Terraform and redeploy
# Edit infra/envs/prod/terraform.tfvars — override the table name variable
# then run: bash scripts/deploy-infra.sh --env prod --auto-approve

# Option 2 (emergency): Update Lambda env var directly (bypasses Terraform state)
aws lambda update-function-configuration \
  --function-name "radius-prod-event-normalizer" \
  --environment "Variables={...,IDENTITY_PROFILE_TABLE=${RESTORED_TABLE}}" \
  --region us-east-1
# Repeat for all functions that reference this table.
```

#### Step 5: Delete the broken original (after confirming swap works)

```bash
aws dynamodb delete-table \
  --table-name "radius-prod-${TABLE}" \
  --region us-east-1

# Then rename the restored table back to the original name
# (DynamoDB does not support rename — use Terraform to re-create with the original name
#  pointing to the restored data, or keep the new name and update all Lambda env vars)
```

#### Step 6: Verify deployment

```bash
bash scripts/verify-deployment.sh --env prod
```

---

### Option B — AWS Backup Restore (fallback, point-in-day)

Use this when PITR is unavailable (e.g. table was deleted more than 35 days ago or PITR was not enabled).

```bash
# List available recovery points
aws backup list-recovery-points-by-backup-vault \
  --backup-vault-name "radius-prod-backup-vault" \
  --query 'RecoveryPoints[*].{ARN:RecoveryPointArn,Time:CreationDate,Status:Status}' \
  --output table

# Choose a recovery point ARN and restore
aws backup start-restore-job \
  --recovery-point-arn "arn:aws:backup:us-east-1:ACCOUNT:recovery-point:..." \
  --iam-role-arn "$(aws iam get-role --role-name radius-prod-backup-role --query 'Role.Arn' --output text)" \
  --metadata '{"targetTableName":"radius-prod-identity-profile-backup-restore"}' \
  --resource-type "DynamoDB"
```

---

## Rebuilding Derived Tables

### event-summary

The `event-summary` table is populated by the `Event_Normalizer` Lambda from CloudTrail events. It does not need an explicit restore — as new CloudTrail events arrive, the table will repopulate. Older events (>90 days) have expired and are not needed.

If you need to backfill recent events manually:
```bash
# Inject test events to verify the pipeline is working
python3 scripts/inject-events.py --env prod
```

### trust-relationship

This table is populated organically as CloudTrail events reveal cross-account assume-role patterns. No manual restore is needed — allow 24–48 hours for the table to rebuild from live traffic.

---

## Post-Recovery Checklist

- [ ] All 7 Lambda functions are `Active` (check via `verify-deployment.sh`)
- [ ] All target DynamoDB tables are `ACTIVE`
- [ ] API Gateway endpoints return 200/401 (not 500)
- [ ] CloudTrail trail is logging
- [ ] CloudWatch alarms return to `OK` state
- [ ] Score_Engine has run at least one batch scoring cycle
- [ ] At least one new incident has been detected (confirms detection pipeline)
- [ ] Incident declared closed in your incident management system

---

## Contact and Escalation

If the restore script fails or the swap procedure is unclear:
1. Check CloudWatch Logs for Lambda errors: `/aws/lambda/radius-prod-*`
2. Check DynamoDB table events in the AWS console
3. Refer to `docs/monitoring.md` for alarm runbooks
4. Escalate to the security engineering team
