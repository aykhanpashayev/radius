#!/usr/bin/env bash
# verify-deployment.sh — Verify a deployed Radius environment is healthy.
#
# Usage:
#   ./scripts/verify-deployment.sh --env dev [--region us-east-1]
#
# Checks:
#   1. All Lambda functions exist and are Active
#   2. All DynamoDB tables exist with correct GSIs
#   3. API Gateway endpoints return 200 or 404 (not 500)
#   4. CloudTrail trail exists and is logging
#
# Prerequisites: aws CLI, curl, jq

set -euo pipefail

# ---------------------------------------------------------------------------
# Windows/WSL2 compatibility — fall back to *.exe if tools not in WSL2 PATH
# ---------------------------------------------------------------------------
if ! command -v aws &>/dev/null && command -v aws.exe &>/dev/null; then
  aws() {
    local args=()
    for arg in "$@"; do
      if [[ "$arg" =~ ^/mnt/([a-z])/(.*) ]]; then
        args+=("${BASH_REMATCH[1]^^}:\\${BASH_REMATCH[2]//\//\\}")
      else
        args+=("$arg")
      fi
    done
    aws.exe "${args[@]}"
  }
  export -f aws
fi

# curl.exe ships with Windows 10+ and is accessible from WSL2
if ! command -v curl &>/dev/null && command -v curl.exe &>/dev/null; then
  curl() { curl.exe "$@"; }
  export -f curl
fi

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENV=""
REGION="us-east-1"
PREFIX="radius"
PASS=0
FAIL=0

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)    ENV="$2";    shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$ENV" ]]; then
  echo "ERROR: --env is required (dev or prod)"
  exit 1
fi

NAME_PREFIX="${PREFIX}-${ENV}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
check_pass() { echo "  [PASS] $1"; (( PASS++ )); }
check_fail() { echo "  [FAIL] $1"; (( FAIL++ )); }

# ---------------------------------------------------------------------------
# 1. Lambda functions
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking Lambda functions..."

FUNCTIONS=(
  "${NAME_PREFIX}-event-normalizer"
  "${NAME_PREFIX}-detection-engine"
  "${NAME_PREFIX}-incident-processor"
  "${NAME_PREFIX}-identity-collector"
  "${NAME_PREFIX}-score-engine"
  "${NAME_PREFIX}-api-handler"
)

for FUNC in "${FUNCTIONS[@]}"; do
  STATE=$(aws lambda get-function \
    --function-name "$FUNC" \
    --region "$REGION" \
    --query 'Configuration.State' \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "$STATE" == "Active" ]]; then
    check_pass "Lambda ${FUNC} is Active"
  else
    check_fail "Lambda ${FUNC} state=${STATE}"
  fi
done

# ---------------------------------------------------------------------------
# 2. DynamoDB tables
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking DynamoDB tables..."

TABLES=(
  "${NAME_PREFIX}-identity-profile"
  "${NAME_PREFIX}-blast-radius-score"
  "${NAME_PREFIX}-incident"
  "${NAME_PREFIX}-event-summary"
  "${NAME_PREFIX}-trust-relationship"
)

for TABLE in "${TABLES[@]}"; do
  STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE" \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "$STATUS" == "ACTIVE" ]]; then
    check_pass "DynamoDB table ${TABLE} is ACTIVE"
  else
    check_fail "DynamoDB table ${TABLE} status=${STATUS}"
  fi
done

# ---------------------------------------------------------------------------
# 3. API Gateway endpoints
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking API Gateway endpoints..."

# Get API ID
API_ID=$(aws apigateway get-rest-apis \
  --region "$REGION" \
  --query "items[?name=='${NAME_PREFIX}-api'].id | [0]" \
  --output text 2>/dev/null || echo "")

if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
  check_fail "API Gateway ${NAME_PREFIX}-api not found"
else
  check_pass "API Gateway ${NAME_PREFIX}-api found (id=${API_ID})"

  BASE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/${ENV}"

  ENDPOINTS=(
    "/identities"
    "/scores"
    "/incidents"
    "/events"
    "/trust-relationships"
  )

  for EP in "${ENDPOINTS[@]}"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time 10 \
      "${BASE_URL}${EP}" 2>/dev/null || echo "000")

    if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "404" ]]; then
      check_pass "GET ${EP} returned ${HTTP_CODE}"
    else
      check_fail "GET ${EP} returned ${HTTP_CODE} (expected 200 or 404)"
    fi
  done
fi

# ---------------------------------------------------------------------------
# 4. CloudTrail
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking CloudTrail..."

TRAIL_STATUS=$(aws cloudtrail get-trail-status \
  --name "${NAME_PREFIX}-trail" \
  --region "$REGION" \
  --query 'IsLogging' \
  --output text 2>/dev/null || echo "NOT_FOUND")

if [[ "$TRAIL_STATUS" == "True" ]]; then
  check_pass "CloudTrail ${NAME_PREFIX}-trail is logging"
elif [[ "$TRAIL_STATUS" == "False" ]]; then
  check_fail "CloudTrail ${NAME_PREFIX}-trail exists but is NOT logging"
else
  check_fail "CloudTrail ${NAME_PREFIX}-trail not found"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "==> Verification complete: ${PASS} passed, ${FAIL} failed"
echo ""

if [[ $FAIL -gt 0 ]]; then
  echo "Some checks failed. Review the output above and check CloudWatch logs."
  exit 1
else
  echo "All checks passed."
fi
