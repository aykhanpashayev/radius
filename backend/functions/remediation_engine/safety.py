"""Remediation_Engine safety controls.

check_safety_controls() evaluates four guards in order:
  1. excluded_arns — identity explicitly excluded from remediation
  2. protected_account_ids — identity belongs to a protected AWS account
  3. 60-minute cooldown — a remediation was already executed recently
  4. 24-hour rate limit — max 10 executions per identity per day
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

_COOLDOWN_MINUTES = 60
_RATE_LIMIT_HOURS = 24
_RATE_LIMIT_MAX = 10


def check_safety_controls(
    identity_arn: str,
    config: dict[str, Any],
    audit_table: str,
) -> str | None:
    """Check all safety controls for the given identity.

    Checks in order:
      1. excluded_arns list
      2. protected_account_ids list
      3. 60-minute cooldown
      4. 24-hour rate limit (max 10 executions)

    Args:
        identity_arn: ARN of the identity being remediated.
        config: Loaded config dict from load_config().
        audit_table: Name of the Remediation_Audit_Log DynamoDB table.

    Returns:
        A suppression reason string if any control fires, or None to proceed.
    """
    # 1. Excluded ARNs
    excluded_arns: list[str] = config.get("excluded_arns") or []
    if identity_arn in excluded_arns:
        logger.info("Safety: identity excluded", extra={"identity_arn": identity_arn})
        return "identity_excluded"

    # 2. Protected account IDs
    account_id = _extract_account_id(identity_arn)
    protected_accounts: list[str] = config.get("protected_account_ids") or []
    if account_id and account_id in protected_accounts:
        logger.info(
            "Safety: account protected",
            extra={"identity_arn": identity_arn, "account_id": account_id},
        )
        return "account_protected"

    # 3. 60-minute cooldown
    recent_executions = _query_recent_executions(audit_table, identity_arn, hours=1)
    if recent_executions > 0:
        logger.info(
            "Safety: cooldown active",
            extra={"identity_arn": identity_arn, "recent_executions": recent_executions},
        )
        return "cooldown_active"

    # 4. 24-hour rate limit
    daily_executions = _query_recent_executions(audit_table, identity_arn, hours=_RATE_LIMIT_HOURS)
    if daily_executions >= _RATE_LIMIT_MAX:
        logger.info(
            "Safety: rate limit reached",
            extra={"identity_arn": identity_arn, "daily_executions": daily_executions},
        )
        return "rate_limit_exceeded"

    return None


def _query_recent_executions(
    audit_table: str,
    identity_arn: str,
    hours: int,
) -> int:
    """Count audit entries with outcome=executed for identity_arn within the last N hours.

    Uses the IdentityTimeIndex GSI (PK: identity_arn, SK: timestamp).

    Args:
        audit_table: Name of the Remediation_Audit_Log DynamoDB table.
        identity_arn: ARN of the identity to query.
        hours: How many hours back to look.

    Returns:
        Count of matching audit entries.
    """
    now = datetime.now(tz=timezone.utc)
    cutoff = datetime.fromtimestamp(
        now.timestamp() - hours * 3600, tz=timezone.utc
    ).isoformat()

    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(audit_table)

    try:
        response = table.query(
            IndexName="IdentityTimeIndex",
            KeyConditionExpression=(
                Key("identity_arn").eq(identity_arn)
                & Key("timestamp").gte(cutoff)
            ),
            FilterExpression=Attr("outcome").eq("executed"),
            Select="COUNT",
        )
        return response.get("Count", 0)
    except Exception as exc:
        # Non-fatal: if we can't query, allow remediation to proceed
        logger.warning(
            "Safety: failed to query audit table (allowing remediation)",
            extra={"identity_arn": identity_arn, "error": str(exc)},
        )
        return 0


def _extract_account_id(identity_arn: str) -> str | None:
    """Extract the 12-digit AWS account ID from an ARN.

    ARN format: arn:partition:service:region:account-id:resource

    Args:
        identity_arn: Full IAM ARN string.

    Returns:
        Account ID string, or None if the ARN is malformed.
    """
    parts = identity_arn.split(":")
    if len(parts) >= 5 and parts[4]:
        return parts[4]
    return None
