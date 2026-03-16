#!/usr/bin/env bash
# deploy-infra.sh — Initialize and apply Terraform for a Radius environment.
#
# Usage:
#   ./scripts/deploy-infra.sh --env dev [--auto-approve] [--plan-only]
#
# Prerequisites: terraform >= 1.5, aws CLI with credentials configured

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENV=""
AUTO_APPROVE=false
PLAN_ONLY=false
INFRA_ROOT="$(pwd)/infra"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)          ENV="$2";       shift 2 ;;
    --auto-approve) AUTO_APPROVE=true; shift ;;
    --plan-only)    PLAN_ONLY=true;    shift ;;
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

echo "==> Deploying Radius infrastructure [env=${ENV}]"
echo "    Directory : ${ENV_DIR}"
echo "    Backend   : ${BACKEND_VARS}"
echo "    Variables : ${TFVARS}"
echo ""

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------
echo "--> terraform init"
terraform -chdir="$ENV_DIR" init \
  -backend-config="$BACKEND_VARS" \
  -reconfigure \
  -input=false

# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
PLAN_FILE="${ENV_DIR}/.tfplan"
echo ""
echo "--> terraform plan"
terraform -chdir="$ENV_DIR" plan \
  -var-file="$TFVARS" \
  -out="$PLAN_FILE" \
  -input=false

if [[ "$PLAN_ONLY" == "true" ]]; then
  echo ""
  echo "==> Plan complete (--plan-only). No changes applied."
  exit 0
fi

# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------
echo ""
if [[ "$AUTO_APPROVE" == "true" ]]; then
  echo "--> terraform apply (auto-approved)"
  terraform -chdir="$ENV_DIR" apply "$PLAN_FILE"
else
  echo "--> terraform apply"
  read -r -p "Apply the above plan? [yes/no]: " CONFIRM
  if [[ "$CONFIRM" != "yes" ]]; then
    echo "Aborted."
    exit 0
  fi
  terraform -chdir="$ENV_DIR" apply "$PLAN_FILE"
fi

# ---------------------------------------------------------------------------
# Output resource ARNs
# ---------------------------------------------------------------------------
echo ""
echo "==> Deployment complete. Resource outputs:"
terraform -chdir="$ENV_DIR" output -json | \
  python3 -c "
import json, sys
outputs = json.load(sys.stdin)
for k, v in outputs.items():
    print(f'  {k} = {v[\"value\"]}')
"

rm -f "$PLAN_FILE"
echo ""
echo "==> Done."
