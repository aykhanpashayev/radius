#!/usr/bin/env bash
# deploy-infra.sh — Initialize and apply Terraform for a Radius environment.
#
# Usage:
#   ./scripts/deploy-infra.sh --env dev [--auto-approve] [--plan-only]
#
# What this does:
#   1. Runs terraform init with the backend config from infra/envs/<env>/backend.tfvars
#   2. Runs terraform plan using infra/envs/<env>/terraform.tfvars
#   3. Prompts for confirmation, then applies (unless --plan-only)
#
# Prerequisites:
#   - Terraform >= 1.5 installed and on PATH
#   - AWS CLI configured: run "aws sts get-caller-identity" to verify
#   - infra/envs/<env>/backend.tfvars filled in (copy from the template)
#   - infra/envs/<env>/terraform.tfvars filled in (copy from the template)
#   - S3 bucket for Terraform state already created
#   - S3 bucket for Lambda packages already created and set in terraform.tfvars
#
# Windows users: run this script inside WSL2 or Git Bash.

set -euo pipefail

# ---------------------------------------------------------------------------
# Windows/WSL2 compatibility
# Converts /mnt/c/foo/bar → C:\foo\bar for Windows .exe tools
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

if ! command -v terraform &>/dev/null && command -v terraform.exe &>/dev/null; then
  terraform() {
    local a=()
    for x in "$@"; do
      # Handle -chdir=/mnt/... style flags
      if [[ "$x" =~ ^(-chdir=)(/mnt/[a-z]/.*)$ ]]; then
        a+=("${BASH_REMATCH[1]}$(_winpath "${BASH_REMATCH[2]}")")
      # Handle -backend-config=/mnt/... and -var-file=/mnt/... style flags
      elif [[ "$x" =~ ^(-[a-z-]+=)(/mnt/[a-z]/.*)$ ]]; then
        a+=("${BASH_REMATCH[1]}$(_winpath "${BASH_REMATCH[2]}")")
      else
        a+=("$(_winpath "$x")")
      fi
    done
    terraform.exe "${a[@]}"
  }
  export -f terraform _winpath
fi

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENV=""
AUTO_APPROVE=false
PLAN_ONLY=false
EXTRA_VARS=()
# The env dirs live under infra/envs/<env>/ and contain their own main.tf
# which calls the root module via source = "../.."
INFRA_ROOT="$(pwd)/infra"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)          ENV="$2";                           shift 2 ;;
    --auto-approve) AUTO_APPROVE=true;                  shift ;;
    --plan-only)    PLAN_ONLY=true;                     shift ;;
    --var)          EXTRA_VARS+=("-var" "$2");           shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$ENV" ]]; then
  echo "ERROR: --env is required (dev or prod)"
  exit 1
fi

ENV_DIR="${INFRA_ROOT}/envs/${ENV}"
BACKEND_VARS="${ENV_DIR}/backend.tfvars"
TFVARS="${ENV_DIR}/terraform.tfvars"

if [[ ! -d "$ENV_DIR" ]]; then
  echo "ERROR: Environment directory not found: ${ENV_DIR}"
  exit 1
fi

# Check for placeholder values that haven't been filled in
if grep -qE 'TODO:|<REPLACE:' "$TFVARS" 2>/dev/null; then
  echo "ERROR: ${TFVARS} still contains unfilled placeholder values."
  echo "       Open the file and replace every value marked TODO: or <REPLACE:...>"
  exit 1
fi

if grep -qE 'TODO:|<REPLACE:' "$BACKEND_VARS" 2>/dev/null; then
  echo "ERROR: ${BACKEND_VARS} still contains unfilled placeholder values."
  echo "       Open the file and replace every value marked TODO: or <REPLACE:...>"
  exit 1
fi

echo "==> Deploying Radius infrastructure [env=${ENV}]"
echo "    Env dir   : ${ENV_DIR}"
echo "    Backend   : ${BACKEND_VARS}"
echo "    Variables : ${TFVARS}"
echo ""

# ---------------------------------------------------------------------------
# Init — configure the S3 backend and download providers
# ---------------------------------------------------------------------------
echo "--> terraform init"
terraform -chdir="${ENV_DIR}" init \
  -backend-config="${BACKEND_VARS}" \
  -reconfigure \
  -input=false

# ---------------------------------------------------------------------------
# Plan — show what will be created/changed/destroyed
# ---------------------------------------------------------------------------
PLAN_FILE="${ENV_DIR}/.tfplan"
echo ""
echo "--> terraform plan"
terraform -chdir="${ENV_DIR}" plan \
  -var-file="${TFVARS}" \
  "${EXTRA_VARS[@]}" \
  -out="${PLAN_FILE}" \
  -input=false

if [[ "$PLAN_ONLY" == "true" ]]; then
  echo ""
  echo "==> Plan complete (--plan-only). No changes applied."
  rm -f "${PLAN_FILE}"
  exit 0
fi

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
echo ""
if [[ "$AUTO_APPROVE" == "true" ]]; then
  echo "--> terraform apply (auto-approved)"
  terraform -chdir="${ENV_DIR}" apply "${PLAN_FILE}"
else
  echo "--> terraform apply"
  read -r -p "Apply the above plan? [yes/no]: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    rm -f "${PLAN_FILE}"
    exit 0
  fi
  terraform -chdir="${ENV_DIR}" apply "${PLAN_FILE}"
fi

rm -f "${PLAN_FILE}"

# ---------------------------------------------------------------------------
# Print outputs
# ---------------------------------------------------------------------------
echo ""
echo "==> Deployment complete. Key outputs:"
terraform -chdir="${ENV_DIR}" output -json 2>/dev/null | \
  python3 -c "
import json, sys
try:
    outputs = json.load(sys.stdin)
    for k, v in outputs.items():
        val = v.get('value', '')
        if isinstance(val, str):
            print(f'  {k} = {val}')
except Exception:
    pass
" || true

echo ""
echo "==> Next step: run ./scripts/verify-deployment.sh --env ${ENV}"
