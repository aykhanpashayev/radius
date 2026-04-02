#!/usr/bin/env bash
# preflight.sh — Check all prerequisites before deploying Radius.
#
# Usage:
#   ./scripts/preflight.sh [--env dev] [--skip-aws]
#
# What this checks:
#   - OS and shell environment
#   - Required CLI tools and their versions
#   - Python version and required packages
#   - AWS credentials (unless --skip-aws)
#   - Required config files exist and have been filled in
#
# Run this before build-lambdas.sh or deploy-infra.sh.
# Fix every [FAIL] before proceeding.

set -euo pipefail

ENV="dev"
SKIP_AWS=false
PASS=0
FAIL=0
WARN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)      ENV="$2"; shift 2 ;;
    --skip-aws) SKIP_AWS=true; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
ok()   { echo "  [PASS] $1"; (( PASS++ )) || true; }
fail() { echo "  [FAIL] $1"; (( FAIL++ )) || true; }
warn() { echo "  [WARN] $1"; (( WARN++ )) || true; }
section() { echo ""; echo "==> $1"; }

# ---------------------------------------------------------------------------
# 1. OS / Shell
# ---------------------------------------------------------------------------
section "Environment"

OS="$(uname -s 2>/dev/null || echo 'Unknown')"
case "$OS" in
  Linux*)  ok "OS: Linux" ;;
  Darwin*) ok "OS: macOS" ;;
  MINGW*|MSYS*|CYGWIN*) warn "OS: Windows (Git Bash/MSYS) — deployment scripts require bash; WSL2 is recommended for full compatibility" ;;
  *) warn "OS: ${OS} — untested environment" ;;
esac

if [[ -n "${WSL_DISTRO_NAME:-}" ]]; then
  ok "Running inside WSL2 (${WSL_DISTRO_NAME})"
fi

# ---------------------------------------------------------------------------
# 2. Required CLI tools
# ---------------------------------------------------------------------------
section "Required tools"

# Python 3.11+
if command -v python3 &>/dev/null; then
  PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -ge 11 ]]; then
    ok "Python ${PY_VER}"
  else
    fail "Python ${PY_VER} — need 3.11 or higher. Download from https://python.org"
  fi
elif command -v python &>/dev/null; then
  PY_VER=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
  PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
  if [[ "$PY_MAJOR" -eq 3 && "$PY_MINOR" -ge 11 ]]; then
    ok "Python ${PY_VER} (via 'python' command)"
  else
    fail "Python ${PY_VER} — need 3.11 or higher"
  fi
else
  fail "Python not found — install from https://python.org"
fi

# pip
if command -v pip3 &>/dev/null || command -v pip &>/dev/null; then
  PIP_CMD=$(command -v pip3 || command -v pip)
  PIP_VER=$($PIP_CMD --version 2>/dev/null | awk '{print $2}')
  ok "pip ${PIP_VER}"
else
  fail "pip not found — install Python 3.11+ which includes pip"
fi

# zip (needed by build-lambdas.sh)
if command -v zip &>/dev/null; then
  ok "zip $(zip --version 2>&1 | head -1 | awk '{print $2}')"
else
  fail "zip not found — install with: sudo apt install zip (Linux) or brew install zip (macOS)"
fi

# Terraform
if command -v terraform &>/dev/null; then
  TF_VER=$(terraform version -json 2>/dev/null | python3 -c "import json,sys; print(json.load(sys.stdin)['terraform_version'])" 2>/dev/null || terraform version | head -1 | awk '{print $2}' | tr -d 'v')
  TF_MAJOR=$(echo "$TF_VER" | cut -d. -f1)
  TF_MINOR=$(echo "$TF_VER" | cut -d. -f2)
  if [[ "$TF_MAJOR" -ge 1 && "$TF_MINOR" -ge 5 ]]; then
    ok "Terraform ${TF_VER}"
  else
    fail "Terraform ${TF_VER} — need >= 1.5.0. Download from https://developer.hashicorp.com/terraform/downloads"
  fi
else
  fail "Terraform not found — download from https://developer.hashicorp.com/terraform/downloads"
fi

# AWS CLI
if command -v aws &>/dev/null; then
  AWS_VER=$(aws --version 2>&1 | awk '{print $1}' | cut -d/ -f2)
  ok "AWS CLI ${AWS_VER}"
else
  if [[ "$SKIP_AWS" == "true" ]]; then
    warn "AWS CLI not found (--skip-aws set, continuing)"
  else
    fail "AWS CLI not found — install from https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
  fi
fi

# jq (used by some scripts)
if command -v jq &>/dev/null; then
  ok "jq $(jq --version)"
else
  warn "jq not found — optional but useful for debugging. Install: sudo apt install jq / brew install jq"
fi

# ---------------------------------------------------------------------------
# 3. Python packages
# ---------------------------------------------------------------------------
section "Python packages"

PYTHON_CMD=$(command -v python3 || command -v python)
check_pkg() {
  local pkg="$1"
  local min_ver="${2:-}"
  if $PYTHON_CMD -c "import $pkg" 2>/dev/null; then
    if [[ -n "$min_ver" ]]; then
      ok "Python package: ${pkg}"
    else
      ok "Python package: ${pkg}"
    fi
  else
    fail "Python package '${pkg}' not installed — run: pip install -r backend/requirements-dev.txt"
  fi
}

check_pkg "boto3"
check_pkg "moto"
check_pkg "pytest"
check_pkg "hypothesis"

if $PYTHON_CMD -c "import pytest_cov" 2>/dev/null; then
  ok "Python package: pytest-cov"
else
  fail "Python package 'pytest-cov' not installed — run: pip install -r backend/requirements-dev.txt"
fi

# ---------------------------------------------------------------------------
# 4. AWS credentials
# ---------------------------------------------------------------------------
if [[ "$SKIP_AWS" == "false" ]]; then
  section "AWS credentials"

  if aws sts get-caller-identity &>/dev/null; then
    ACCOUNT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
    ARN=$(aws sts get-caller-identity --query Arn --output text 2>/dev/null)
    ok "AWS credentials valid"
    ok "Account: ${ACCOUNT}"
    ok "Identity: ${ARN}"
  else
    fail "AWS credentials not configured or expired — run: aws configure"
  fi
fi

# ---------------------------------------------------------------------------
# 5. Config files
# ---------------------------------------------------------------------------
section "Config files [env=${ENV}]"

ENV_DIR="infra/envs/${ENV}"

if [[ -f "${ENV_DIR}/terraform.tfvars" ]]; then
  if grep -qF "<REPLACE" "${ENV_DIR}/terraform.tfvars"; then
    UNFILLED=$(grep -nF "<REPLACE" "${ENV_DIR}/terraform.tfvars" | awk -F: '{print "    line "$1": "$2}')
    fail "${ENV_DIR}/terraform.tfvars still has unfilled placeholders:
${UNFILLED}"
  else
    ok "${ENV_DIR}/terraform.tfvars"
  fi
else
  fail "${ENV_DIR}/terraform.tfvars not found — copy the example and fill in your values:
    cp ${ENV_DIR}/terraform.tfvars.example ${ENV_DIR}/terraform.tfvars"
fi

if [[ -f "${ENV_DIR}/backend.tfvars" ]]; then
  if grep -qF "<REPLACE" "${ENV_DIR}/backend.tfvars"; then
    UNFILLED=$(grep -nF "<REPLACE" "${ENV_DIR}/backend.tfvars" | awk -F: '{print "    line "$1": "$2}')
    fail "${ENV_DIR}/backend.tfvars still has unfilled placeholders:
${UNFILLED}"
  else
    ok "${ENV_DIR}/backend.tfvars"
  fi
else
  fail "${ENV_DIR}/backend.tfvars not found — copy the example and fill in your values:
    cp ${ENV_DIR}/backend.tfvars.example ${ENV_DIR}/backend.tfvars"
fi

if [[ -f "backend/requirements-dev.txt" ]]; then
  ok "backend/requirements-dev.txt"
else
  fail "backend/requirements-dev.txt not found"
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Preflight summary: ${PASS} passed, ${WARN} warnings, ${FAIL} failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ $FAIL -gt 0 ]]; then
  echo ""
  echo "Fix the [FAIL] items above before proceeding."
  echo "See docs/deployment.md for detailed instructions."
  exit 1
else
  echo ""
  echo "All required checks passed."
  if [[ $WARN -gt 0 ]]; then
    echo "Review the [WARN] items above — they may affect deployment."
  fi
  echo ""
  echo "Next steps:"
  echo "  1. pip install -r backend/requirements-dev.txt"
  echo "  2. bash scripts/run-tests.sh"
  echo "  3. bash scripts/build-lambdas.sh --env ${ENV} --bucket <your-bucket>"
  echo "  4. bash scripts/deploy-infra.sh --env ${ENV}"
  echo "  5. bash scripts/verify-deployment.sh --env ${ENV}"
fi
