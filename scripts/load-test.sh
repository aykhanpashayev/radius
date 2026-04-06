#!/usr/bin/env bash
# load-test.sh — Run a Locust load test against a deployed Radius API.
#
# Usage:
#   bash scripts/load-test.sh \
#     --env prod \
#     --users 20 \
#     --spawn-rate 2 \
#     --duration 5m \
#     [--jwt <token>] \
#     [--username <cognito-user>] \
#     [--password <cognito-password>] \
#     [--region us-east-1]
#
# Authentication: provide EITHER --jwt (pre-obtained token) OR
# --username + --password (the script will obtain a token from Cognito).
#
# After the test, inspect CloudWatch metrics to tune alarm thresholds:
#   - Observe Lambda Duration (p99) vs the 24 000 ms alarm threshold
#   - Observe API Gateway Latency vs expected response times
#   - Compare with docs/runbooks/load-testing.md baselines

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
ENV=""
USERS=20
SPAWN_RATE=2
DURATION="5m"
JWT=""
USERNAME=""
PASSWORD=""
REGION="us-east-1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)        ENV="$2";        shift 2 ;;
    --users)      USERS="$2";      shift 2 ;;
    --spawn-rate) SPAWN_RATE="$2"; shift 2 ;;
    --duration)   DURATION="$2";   shift 2 ;;
    --jwt)        JWT="$2";        shift 2 ;;
    --username)   USERNAME="$2";   shift 2 ;;
    --password)   PASSWORD="$2";   shift 2 ;;
    --region)     REGION="$2";     shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$ENV" ]]; then
  echo "ERROR: --env is required (dev or prod)"
  exit 1
fi

# ---------------------------------------------------------------------------
# Install locust if not present
# ---------------------------------------------------------------------------
if ! command -v locust &>/dev/null; then
  echo "--> Installing locust..."
  pip install --quiet "locust>=2.20.0"
fi

# ---------------------------------------------------------------------------
# Fetch API URL from SSM
# ---------------------------------------------------------------------------
echo "==> Fetching API config from SSM [env=${ENV}]..."
API_URL=$(aws ssm get-parameter \
  --name "/radius/${ENV}/api/endpoint" \
  --region "${REGION}" \
  --query "Parameter.Value" \
  --output text)
echo "    API_URL: ${API_URL}"

# ---------------------------------------------------------------------------
# Obtain JWT: either from --jwt flag or by authenticating with Cognito
# ---------------------------------------------------------------------------
if [[ -z "$JWT" ]]; then
  if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
    echo ""
    echo "ERROR: Provide either --jwt <token> OR both --username and --password."
    echo ""
    echo "  To get a JWT manually:"
    echo "    1. Open the Radius dashboard in a browser"
    echo "    2. Open DevTools → Network → find any API call"
    echo "    3. Copy the Authorization header value (without 'Bearer ')"
    echo "    4. Pass it as --jwt <token>"
    exit 1
  fi

  echo ""
  echo "--> Obtaining Cognito JWT for user: ${USERNAME}"

  CLIENT_ID=$(aws ssm get-parameter \
    --name "/radius/${ENV}/cognito/client_id" \
    --region "${REGION}" \
    --query "Parameter.Value" \
    --output text)

  JWT=$(aws cognito-idp initiate-auth \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "${CLIENT_ID}" \
    --auth-parameters "USERNAME=${USERNAME},PASSWORD=${PASSWORD}" \
    --region "${REGION}" \
    --query "AuthenticationResult.IdToken" \
    --output text 2>/dev/null)

  if [[ -z "$JWT" || "$JWT" == "None" ]]; then
    echo "ERROR: Failed to obtain JWT. Check username/password and try again."
    exit 1
  fi

  echo "    Token obtained."
fi

# ---------------------------------------------------------------------------
# Run load test
# ---------------------------------------------------------------------------
RESULTS_DIR=".load-test-results"
mkdir -p "${RESULTS_DIR}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
RESULTS_FILE="${RESULTS_DIR}/results-${ENV}-${TIMESTAMP}"

echo ""
echo "==> Starting load test"
echo "    Users       : ${USERS}"
echo "    Spawn rate  : ${SPAWN_RATE}/s"
echo "    Duration    : ${DURATION}"
echo "    Results     : ${RESULTS_FILE}_*.csv"
echo ""

export LOAD_TEST_API_URL="${API_URL}"
export LOAD_TEST_JWT="${JWT}"

locust \
  -f scripts/locustfile.py \
  --headless \
  --users "${USERS}" \
  --spawn-rate "${SPAWN_RATE}" \
  --run-time "${DURATION}" \
  --csv "${RESULTS_FILE}" \
  --html "${RESULTS_FILE}.html" \
  --exit-code-on-error 1

echo ""
echo "==> Load test complete."
echo "    HTML report : ${RESULTS_FILE}.html"
echo "    CSV data    : ${RESULTS_FILE}_stats.csv"
echo ""
echo "Next: compare p50/p95/p99 latencies against baselines in"
echo "      docs/runbooks/load-testing.md and tune CloudWatch alarm"
echo "      thresholds if needed."
