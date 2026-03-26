#!/usr/bin/env bash
# build-lambdas.sh — Package all Radius Lambda functions and upload to S3.
#
# Usage:
#   ./scripts/build-lambdas.sh --env dev [--bucket my-bucket] [--region us-east-1]
#   ./scripts/build-lambdas.sh --env dev --local   # build only, skip S3 upload
#
# What this does:
#   1. For each Lambda function, installs its Python dependencies into a build dir
#   2. Copies backend/common/ shared utilities into each package
#   3. Zips the package (excluding .pyc and __pycache__)
#   4. Uploads each zip to s3://<bucket>/functions/<name>.zip (unless --local)
#
# Prerequisites:
#   - python3 and pip
#   - zip (Linux/macOS: built-in; Windows: use WSL2 or Git Bash)
#   - aws CLI configured (only needed without --local)
#
# Windows users: run this script inside WSL2 or Git Bash.
# See docs/deployment.md for Windows setup instructions.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENV=""
BUCKET=""
REGION="us-east-1"
LOCAL_ONLY=false
BUILD_DIR="$(pwd)/.build"
FUNCTIONS_DIR="$(pwd)/backend/functions"
COMMON_DIR="$(pwd)/backend/common"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env)     ENV="$2";    shift 2 ;;
    --bucket)  BUCKET="$2"; shift 2 ;;
    --region)  REGION="$2"; shift 2 ;;
    --local)   LOCAL_ONLY=true; shift ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$ENV" ]]; then
  echo "ERROR: --env is required (dev or prod)"
  exit 1
fi

# Try to read bucket from tfvars if not provided
if [[ -z "$BUCKET" && "$LOCAL_ONLY" == "false" ]]; then
  TFVARS="$(pwd)/infra/envs/${ENV}/terraform.tfvars"
  if [[ -f "$TFVARS" ]]; then
    BUCKET=$(grep 'lambda_s3_bucket' "$TFVARS" 2>/dev/null | sed 's/.*= *"\(.*\)"/\1/' || true)
  fi
fi

if [[ -z "$BUCKET" && "$LOCAL_ONLY" == "false" ]]; then
  echo "ERROR: --bucket is required (or set lambda_s3_bucket in terraform.tfvars, or use --local)"
  exit 1
fi

if [[ "$LOCAL_ONLY" == "true" ]]; then
  echo "==> Building Lambda packages locally (no S3 upload) [env=${ENV}]"
else
  echo "==> Building Lambda functions [env=${ENV}, bucket=${BUCKET}, region=${REGION}]"
fi

# ---------------------------------------------------------------------------
# Functions to build — must include ALL Lambda functions
# ---------------------------------------------------------------------------
FUNCTION_NAMES=(
  event_normalizer
  detection_engine
  incident_processor
  identity_collector
  score_engine
  api_handler
  remediation_engine
)

SUCCESS_COUNT=0
FAIL_COUNT=0

# ---------------------------------------------------------------------------
# Build loop
# ---------------------------------------------------------------------------
for FUNC in "${FUNCTION_NAMES[@]}"; do
  FUNC_DIR="${FUNCTIONS_DIR}/${FUNC}"
  PACKAGE_DIR="${BUILD_DIR}/${FUNC}"
  ZIP_FILE="${BUILD_DIR}/${FUNC}.zip"

  echo ""
  echo "--> Building ${FUNC}..."

  if [[ ! -d "$FUNC_DIR" ]]; then
    echo "    WARN: ${FUNC_DIR} not found — skipping"
    continue
  fi

  # Clean previous build
  rm -rf "$PACKAGE_DIR"
  mkdir -p "$PACKAGE_DIR"

  # Copy function code
  cp -r "${FUNC_DIR}/." "$PACKAGE_DIR/"

  # Copy shared common utilities
  mkdir -p "${PACKAGE_DIR}/backend/common"
  cp -r "${COMMON_DIR}/." "${PACKAGE_DIR}/backend/common/"
  touch "${PACKAGE_DIR}/backend/__init__.py"

  # Install dependencies
  # NOTE: We do NOT use --platform here because that requires --only-binary
  # and breaks on many packages. Lambda arm64 packages are handled by Terraform
  # layer configuration. For local builds, install native packages normally.
  REQUIREMENTS="${FUNC_DIR}/requirements.txt"
  if [[ -f "$REQUIREMENTS" ]]; then
    pip install \
      --quiet \
      --target "$PACKAGE_DIR" \
      --requirement "$REQUIREMENTS" \
      2>&1 | tail -3
  fi

  # Create zip
  rm -f "$ZIP_FILE"
  (cd "$PACKAGE_DIR" && zip -r "$ZIP_FILE" . \
    -x "*.pyc" \
    -x "*/__pycache__/*" \
    -x "*.dist-info/*" \
    -x "*.egg-info/*") > /dev/null

  ZIP_SIZE=$(du -sh "$ZIP_FILE" | cut -f1)
  echo "    Package: ${ZIP_FILE} (${ZIP_SIZE})"

  if [[ "$LOCAL_ONLY" == "false" ]]; then
    aws s3 cp "$ZIP_FILE" "s3://${BUCKET}/functions/${FUNC}.zip" \
      --region "$REGION" \
      --quiet
    echo "    Uploaded: s3://${BUCKET}/functions/${FUNC}.zip"
  fi

  (( SUCCESS_COUNT++ )) || true
done

echo ""
echo "==> Build complete: ${SUCCESS_COUNT} succeeded, ${FAIL_COUNT} failed"
echo "    Packages in: ${BUILD_DIR}/"

if [[ $FAIL_COUNT -gt 0 ]]; then
  exit 1
fi
