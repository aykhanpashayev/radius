#!/usr/bin/env bash
# build-lambdas.sh — Package all Radius Lambda functions and upload to S3.
#
# Usage:
#   ./scripts/build-lambdas.sh --env dev [--bucket my-bucket] [--region us-east-1]
#
# The script:
#   1. Installs Python dependencies for each function into a build dir
#   2. Zips function code + dependencies
#   3. Uploads each zip to s3://<bucket>/functions/<name>.zip
#
# Prerequisites: python3, pip, zip, aws CLI

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
ENV=""
BUCKET=""
REGION="us-east-1"
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
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

if [[ -z "$ENV" ]]; then
  echo "ERROR: --env is required (dev or prod)"
  exit 1
fi

if [[ -z "$BUCKET" ]]; then
  # Try to read from tfvars
  TFVARS="$(pwd)/infra/envs/${ENV}/terraform.tfvars"
  if [[ -f "$TFVARS" ]]; then
    BUCKET=$(grep 'lambda_s3_bucket' "$TFVARS" | sed 's/.*= *"\(.*\)"/\1/')
  fi
fi

if [[ -z "$BUCKET" ]]; then
  echo "ERROR: --bucket is required (or set lambda_s3_bucket in terraform.tfvars)"
  exit 1
fi

echo "==> Building Lambda functions for env=${ENV}, bucket=${BUCKET}, region=${REGION}"

# ---------------------------------------------------------------------------
# Functions to build
# ---------------------------------------------------------------------------
FUNCTION_NAMES=(
  event_normalizer
  detection_engine
  incident_processor
  identity_collector
  score_engine
  api_handler
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
  REQUIREMENTS="${FUNC_DIR}/requirements.txt"
  if [[ -f "$REQUIREMENTS" ]]; then
    pip install \
      --quiet \
      --target "$PACKAGE_DIR" \
      --requirement "$REQUIREMENTS" \
      --platform manylinux2014_aarch64 \
      --implementation cp \
      --python-version 3.11 \
      --only-binary=:all: \
      2>&1 | tail -5
  fi

  # Create zip
  rm -f "$ZIP_FILE"
  (cd "$PACKAGE_DIR" && zip -r "$ZIP_FILE" . -x "*.pyc" -x "*/__pycache__/*" -x "*.dist-info/*") > /dev/null

  ZIP_SIZE=$(du -sh "$ZIP_FILE" | cut -f1)
  echo "    Package size: ${ZIP_SIZE}"

  # Upload to S3
  aws s3 cp "$ZIP_FILE" "s3://${BUCKET}/functions/${FUNC}.zip" \
    --region "$REGION" \
    --quiet

  echo "    Uploaded to s3://${BUCKET}/functions/${FUNC}.zip"
  (( SUCCESS_COUNT++ ))
done

echo ""
echo "==> Build complete: ${SUCCESS_COUNT} succeeded, ${FAIL_COUNT} failed"

if [[ $FAIL_COUNT -gt 0 ]]; then
  exit 1
fi
