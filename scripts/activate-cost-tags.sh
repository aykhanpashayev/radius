#!/usr/bin/env bash
# activate-cost-tags.sh — Activate Radius cost allocation tags in AWS Cost Explorer.
#
# This is a ONE-TIME operation per AWS account. Run it after the first prod deploy.
# Cost allocation tags must be explicitly activated before they appear in Cost Explorer
# reports — Terraform cannot do this automatically.
#
# Usage:
#   bash scripts/activate-cost-tags.sh [--region us-east-1]
#
# Prerequisites:
#   - AWS CLI configured with billing permissions (ce:UpdateCostAllocationTagsStatus)
#   - Run from the account where Radius is deployed

set -euo pipefail

REGION="us-east-1"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --region) REGION="$2"; shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Tag keys to activate — must match the tags applied by Terraform
# ---------------------------------------------------------------------------
TAG_KEYS=(
  "Project"
  "Environment"
  "ManagedBy"
  "CostCenter"
  "Team"
  "DataClassification"
  "Component"
  "Module"
  "Function"
  "Table"
)

echo "==> Activating cost allocation tags in AWS Cost Explorer"
echo "    Region: ${REGION}"
echo "    Tags  : ${TAG_KEYS[*]}"
echo ""

# Build the JSON payload for the API call
TAGS_JSON="["
for i in "${!TAG_KEYS[@]}"; do
  if [[ $i -gt 0 ]]; then
    TAGS_JSON+=","
  fi
  TAGS_JSON+="{\"TagKey\":\"${TAG_KEYS[$i]}\",\"Status\":\"Active\"}"
done
TAGS_JSON+="]"

aws ce update-cost-allocation-tags-status \
  --cost-allocation-tags-status "${TAGS_JSON}" \
  --region "${REGION}"

echo ""
echo "==> Done. Tag activation may take up to 24 hours to appear in Cost Explorer."
echo "    View at: https://console.aws.amazon.com/billing/home#/tags"
echo ""
echo "    Cost Explorer will show per-tag breakdowns for:"
for KEY in "${TAG_KEYS[@]}"; do
  echo "      - ${KEY}"
done
