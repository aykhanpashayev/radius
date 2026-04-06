#!/usr/bin/env bash
# restore-dynamodb.sh — Restore a Radius DynamoDB table to a point in time.
#
# Uses PITR (Point-In-Time Recovery) to restore a table to a target timestamp.
# The original table is NOT modified — a new table is created with a suffix.
# After validating the restored table, swap traffic manually via the runbook:
#   docs/runbooks/disaster-recovery.md
#
# Usage:
#   bash scripts/restore-dynamodb.sh \
#     --table identity-profile \
#     --restore-time "2026-04-01T10:30:00Z" \
#     --env prod \
#     [--suffix restored] \
#     [--region us-east-1]
#
# Prerequisites:
#   - AWS CLI configured with DynamoDB permissions
#   - PITR must be enabled on the source table (enabled by default in Radius)

set -euo pipefail

# ---------------------------------------------------------------------------
# Windows/WSL2 compatibility
# ---------------------------------------------------------------------------
_winpath() {
  local p="$1"
  if [[ "$p" =~ ^/mnt/([a-z])/(.*)$ ]]; then
    echo "${BASH_REMATCH[1]^^}:\\${BASH_REMATCH[2]//\//\\}"
  else
    echo "$p"
  fi
}

if ! command -v aws &>/dev/null && command -v aws.exe &>/dev/null; then
  aws() {
    local a=()
    for x in "$@"; do a+=("$(_winpath "$x")"); done
    aws.exe "${a[@]}" | tr -d '\r'
  }
  export -f aws _winpath
fi

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
TABLE=""
RESTORE_TIME=""
ENV=""
SUFFIX="restored"
REGION="us-east-1"
PREFIX="radius"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --table)        TABLE="$2";        shift 2 ;;
    --restore-time) RESTORE_TIME="$2"; shift 2 ;;
    --env)          ENV="$2";          shift 2 ;;
    --suffix)       SUFFIX="$2";       shift 2 ;;
    --region)       REGION="$2";       shift 2 ;;
    --prefix)       PREFIX="$2";       shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$TABLE" || -z "$RESTORE_TIME" || -z "$ENV" ]]; then
  echo "ERROR: --table, --restore-time, and --env are required."
  echo ""
  echo "Usage:"
  echo "  bash scripts/restore-dynamodb.sh \\"
  echo "    --table identity-profile \\"
  echo "    --restore-time \"2026-04-01T10:30:00Z\" \\"
  echo "    --env prod"
  exit 1
fi

SOURCE_TABLE="${PREFIX}-${ENV}-${TABLE}"
TARGET_TABLE="${SOURCE_TABLE}-${SUFFIX}"

echo "==> DynamoDB Point-In-Time Restore"
echo "    Source : ${SOURCE_TABLE}"
echo "    Target : ${TARGET_TABLE}"
echo "    Time   : ${RESTORE_TIME}"
echo "    Region : ${REGION}"
echo ""

# Verify source table exists and has PITR enabled
PITR_STATUS=$(aws dynamodb describe-continuous-backups \
  --table-name "${SOURCE_TABLE}" \
  --region "${REGION}" \
  --query 'ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus' \
  --output text 2>/dev/null || echo "ERROR")

if [[ "$PITR_STATUS" == "ERROR" ]]; then
  echo "ERROR: Table ${SOURCE_TABLE} not found in region ${REGION}."
  exit 1
fi

if [[ "$PITR_STATUS" != "ENABLED" ]]; then
  echo "ERROR: PITR is not enabled on ${SOURCE_TABLE} (status=${PITR_STATUS})."
  echo "       Cannot restore — enable PITR first or use AWS Backup."
  exit 1
fi

# Check target table doesn't already exist
EXISTING=$(aws dynamodb describe-table \
  --table-name "${TARGET_TABLE}" \
  --region "${REGION}" \
  --query 'Table.TableStatus' \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$EXISTING" != "NOT_FOUND" ]]; then
  echo "ERROR: Target table ${TARGET_TABLE} already exists (status=${EXISTING})."
  echo "       Choose a different --suffix or delete the existing table first."
  exit 1
fi

# ---------------------------------------------------------------------------
# Initiate restore
# ---------------------------------------------------------------------------
echo "--> Initiating restore..."
aws dynamodb restore-table-to-point-in-time \
  --source-table-name "${SOURCE_TABLE}" \
  --target-table-name "${TARGET_TABLE}" \
  --restore-date-time "${RESTORE_TIME}" \
  --region "${REGION}" \
  --no-cli-pager \
  --output text > /dev/null

echo "    Restore initiated. Polling for completion (this typically takes 2-20 minutes)..."
echo ""

# ---------------------------------------------------------------------------
# Poll until table is ACTIVE
# ---------------------------------------------------------------------------
ELAPSED=0
POLL_INTERVAL=30

while true; do
  STATUS=$(aws dynamodb describe-table \
    --table-name "${TARGET_TABLE}" \
    --region "${REGION}" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "PENDING")

  printf "    [%4ds] Table status: %s\n" "${ELAPSED}" "${STATUS}"

  if [[ "$STATUS" == "ACTIVE" ]]; then
    break
  fi

  if [[ "$STATUS" == "ERROR" || "$STATUS" == "ARCHIVING" ]]; then
    echo ""
    echo "ERROR: Restore failed — table entered status ${STATUS}."
    echo "       Check the AWS console for details."
    exit 1
  fi

  sleep "${POLL_INTERVAL}"
  ELAPSED=$(( ELAPSED + POLL_INTERVAL ))

  # Time out after 45 minutes
  if [[ $ELAPSED -gt 2700 ]]; then
    echo ""
    echo "ERROR: Restore timed out after ${ELAPSED}s. The restore may still be running."
    echo "       Check: aws dynamodb describe-table --table-name ${TARGET_TABLE}"
    exit 1
  fi
done

echo ""
echo "==> Restore complete."
echo ""
echo "    Restored table : ${TARGET_TABLE}"
echo "    Item count     : $(aws dynamodb describe-table \
  --table-name "${TARGET_TABLE}" \
  --region "${REGION}" \
  --query 'Table.ItemCount' \
  --output text 2>/dev/null || echo "N/A")"
echo ""
echo "Next steps:"
echo "  1. Validate the restored table content:"
echo "       aws dynamodb scan --table-name ${TARGET_TABLE} --max-items 5"
echo "  2. If the restore is valid, follow the swap procedure:"
echo "       docs/runbooks/disaster-recovery.md → Traffic Swap section"
echo "  3. Delete the old table once the swap is confirmed:"
echo "       aws dynamodb delete-table --table-name ${SOURCE_TABLE}"
echo "  4. Re-run verify-deployment.sh after the swap:"
echo "       bash scripts/verify-deployment.sh --env ${ENV}"
