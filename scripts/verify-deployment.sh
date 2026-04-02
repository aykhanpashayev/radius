#!/usr/bin/env bash
# verify-deployment.sh — Verify a deployed Radius environment is healthy.
#
# Usage:
#   ./scripts/verify-deployment.sh --env dev [--region us-east-1]
#
# Checks:
#   1. All 7 Lambda functions exist and are Active
#   2. All 7 DynamoDB tables exist and are ACTIVE
#   3. API Gateway exists and endpoints respond (200/401/404 — not 500)
#   4. CloudTrail trail exists and is logging

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
# Helpers — use || true to prevent set -e from firing on counter increment
# ---------------------------------------------------------------------------
check_pass() { echo "  [PASS] $1"; (( PASS++ )) || true; }
check_fail() { echo "  [FAIL] $1"; (( FAIL++ )) || true; }

# ---------------------------------------------------------------------------
# 1. Lambda functions (all 7)
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
  "${NAME_PREFIX}-remediation-engine"
)

for FUNC in "${FUNCTIONS[@]}"; do
  STATE=$(aws lambda get-function \
    --function-name "$FUNC" \
    --region "$REGION" \
    --query 'Configuration.State' \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "$STATE" == "Active" ]]; then
    check_pass "Lambda ${FUNC}"
  else
    check_fail "Lambda ${FUNC} — state=${STATE}"
  fi
done

# ---------------------------------------------------------------------------
# 2. DynamoDB tables (all 7)
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking DynamoDB tables..."

TABLES=(
  "${NAME_PREFIX}-identity-profile"
  "${NAME_PREFIX}-blast-radius-score"
  "${NAME_PREFIX}-incident"
  "${NAME_PREFIX}-event-summary"
  "${NAME_PREFIX}-trust-relationship"
  "${NAME_PREFIX}-remediation-config"
  "${NAME_PREFIX}-remediation-audit-log"
)

for TABLE in "${TABLES[@]}"; do
  STATUS=$(aws dynamodb describe-table \
    --table-name "$TABLE" \
    --region "$REGION" \
    --query 'Table.TableStatus' \
    --output text 2>/dev/null || echo "NOT_FOUND")

  if [[ "$STATUS" == "ACTIVE" ]]; then
    check_pass "DynamoDB ${TABLE}"
  else
    check_fail "DynamoDB ${TABLE} — status=${STATUS}"
  fi
done

# ---------------------------------------------------------------------------
# 3. API Gateway
# ---------------------------------------------------------------------------
echo ""
echo "==> Checking API Gateway..."

API_ID=$(aws apigateway get-rest-apis \
  --region "$REGION" \
  --query "items[?name=='${NAME_PREFIX}-api'].id | [0]" \
  --output text 2>/dev/null || echo "")

if [[ -z "$API_ID" || "$API_ID" == "None" ]]; then
  check_fail "API Gateway ${NAME_PREFIX}-api not found"
else
  check_pass "API Gateway ${NAME_PREFIX}-api exists (id=${API_ID})"

  BASE_URL="https://${API_ID}.execute-api.${REGION}.amazonaws.com/${ENV}"

  ENDPOINTS=(
    "/identities"
    "/scores"
    "/incidents"
    "/events"
    "/trust-relationships"
    "/remediation/config"
    "/remediation/audit"
  )

  for EP in "${ENDPOINTS[@]}"; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
      --max-time 10 \
      "${BASE_URL}${EP}" 2>/dev/null || echo "000")

    # 200 = ok, 401 = auth required (expected with Cognito), 404 = no data yet
    # Anything else (500, 000/timeout) is a real problem
    if [[ "$HTTP_CODE" == "200" || "$HTTP_CODE" == "401" || "$HTTP_CODE" == "404" ]]; then
      check_pass "GET ${EP} → ${HTTP_CODE}"
    else
      check_fail "GET ${EP} → ${HTTP_CODE} (expected 200/401/404)"
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
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Verification: ${PASS} passed, ${FAIL} failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ $FAIL -gt 0 ]]; then
  echo "Some checks failed — review output above and check CloudWatch logs."
  exit 1
else
  echo "All checks passed."
fi
