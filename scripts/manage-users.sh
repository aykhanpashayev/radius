#!/usr/bin/env bash
# manage-users.sh — Create and manage Radius dashboard users in Cognito.
#
# Usage:
#   bash scripts/manage-users.sh --env dev --action create --email user@example.com --password "Str0ng!Pass"
#   bash scripts/manage-users.sh --env dev --action list
#   bash scripts/manage-users.sh --env dev --action delete --email user@example.com
#
# Actions:
#   create  — Create a new user with a permanent password (no force-change required)
#   list    — List all users in the pool
#   delete  — Delete a user

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
# Argument parsing
# ---------------------------------------------------------------------------
ENV=""
ACTION=""
EMAIL=""
PASSWORD=""
REGION="us-east-1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)      ENV="$2";      shift 2 ;;
    --action)   ACTION="$2";   shift 2 ;;
    --email)    EMAIL="$2";    shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --region)   REGION="$2";   shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$ENV" || -z "$ACTION" ]]; then
  echo "Usage: bash scripts/manage-users.sh --env <dev|prod> --action <create|list|delete> [--email EMAIL] [--password PASSWORD]"
  exit 1
fi

# Get User Pool ID from Terraform output
POOL_ID=$(terraform -chdir="infra/envs/${ENV}" output -raw cognito_user_pool_id 2>/dev/null || echo "")
if [[ -z "$POOL_ID" ]]; then
  echo "ERROR: Could not get cognito_user_pool_id from Terraform outputs."
  echo "       Make sure you have deployed the infrastructure: bash scripts/deploy-infra.sh --env ${ENV}"
  exit 1
fi

echo "==> User Pool: ${POOL_ID} [env=${ENV}]"

case "$ACTION" in
  create)
    if [[ -z "$EMAIL" || -z "$PASSWORD" ]]; then
      echo "ERROR: --email and --password are required for create action"
      exit 1
    fi
    echo "--> Creating user: ${EMAIL}"
    aws cognito-idp admin-create-user \
      --user-pool-id "$POOL_ID" \
      --username "$EMAIL" \
      --temporary-password "Temp1234!" \
      --region "$REGION" \
      --output text > /dev/null
    aws cognito-idp admin-set-user-password \
      --user-pool-id "$POOL_ID" \
      --username "$EMAIL" \
      --password "$PASSWORD" \
      --permanent \
      --region "$REGION"
    echo "    [DONE] User ${EMAIL} created with permanent password."
    echo "    They can now sign in at the dashboard."
    ;;

  list)
    echo "--> Listing users:"
    aws cognito-idp list-users \
      --user-pool-id "$POOL_ID" \
      --region "$REGION" \
      --query "Users[*].{Username:Username, Status:UserStatus, Created:UserCreateDate}" \
      --output table
    ;;

  delete)
    if [[ -z "$EMAIL" ]]; then
      echo "ERROR: --email is required for delete action"
      exit 1
    fi
    echo "--> Deleting user: ${EMAIL}"
    aws cognito-idp admin-delete-user \
      --user-pool-id "$POOL_ID" \
      --username "$EMAIL" \
      --region "$REGION"
    echo "    [DONE] User ${EMAIL} deleted."
    ;;

  *)
    echo "ERROR: Unknown action '${ACTION}'. Use: create, list, delete"
    exit 1
    ;;
esac
