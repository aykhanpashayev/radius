"""Identity profile and trust relationship logic for Identity_Collector."""

import re
from datetime import datetime, timezone
from typing import Any

from backend.common.dynamodb_utils import put_item, update_item
from backend.common.errors import ValidationError
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

# Events that indicate identity deletion
_DELETION_EVENTS = {"DeleteUser", "DeleteRole", "DeleteGroup"}

# Events that create trust relationships
_ASSUME_ROLE_EVENTS = {"AssumeRole", "AssumeRoleWithSAML", "AssumeRoleWithWebIdentity"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def extract_identity_type(arn: str) -> str:
    """Derive identity type from ARN structure.

    Args:
        arn: Full IAM identity ARN.

    Returns:
        One of: IAMUser | AssumedRole | AWSService
    """
    if ":user/" in arn:
        return "IAMUser"
    if ":role/" in arn or ":assumed-role/" in arn:
        return "AssumedRole"
    if ":service/" in arn or ":root" in arn:
        return "AWSService"
    return "AWSService"


def extract_account_id(arn: str) -> str:
    """Extract AWS account ID from an ARN.

    Args:
        arn: Full ARN string.

    Returns:
        12-digit account ID string, or empty string if not found.
    """
    parts = arn.split(":")
    if len(parts) >= 5 and parts[4].isdigit():
        return parts[4]
    return ""


def upsert_identity_profile(
    table_name: str,
    identity_arn: str,
    event_summary: dict[str, Any],
) -> None:
    """Create or update an Identity_Profile record.

    Sets last_activity_timestamp on every call. Creates the record if it
    doesn't exist yet (using a conditional put that won't overwrite
    creation_date on existing records).

    Args:
        table_name: Identity_Profile DynamoDB table name.
        identity_arn: Full identity ARN.
        event_summary: Normalized Event_Summary dict.
    """
    now = _utc_now()
    identity_type = extract_identity_type(identity_arn)
    account_id = extract_account_id(identity_arn)

    # Extract tags from CloudTrail metadata if present
    tags = event_summary.get("event_parameters", {}).get("tags", {}) or {}

    update_item(
        table_name=table_name,
        key={"identity_arn": identity_arn},
        update_expression=(
            "SET identity_type = if_not_exists(identity_type, :it), "
            "account_id = if_not_exists(account_id, :aid), "
            "creation_date = if_not_exists(creation_date, :now), "
            "is_active = if_not_exists(is_active, :active), "
            "activity_count = if_not_exists(activity_count, :zero) + :one, "
            "last_activity_timestamp = :now, "
            "#tgs = :tags"
        ),
        expression_attribute_values={
            ":it": identity_type,
            ":aid": account_id,
            ":now": now,
            ":active": True,
            ":zero": 0,
            ":one": 1,
            ":tags": tags,
        },
        expression_attribute_names={"#tgs": "tags"},
    )

    logger.info("Upserted Identity_Profile", extra={
        "identity_arn": identity_arn,
        "identity_type": identity_type,
        "account_id": account_id,
    })


def record_trust_relationship(
    table_name: str,
    event_summary: dict[str, Any],
    raw_event: dict[str, Any],
) -> None:
    """Record a basic trust edge from an AssumeRole event.

    Args:
        table_name: Trust_Relationship DynamoDB table name.
        event_summary: Normalized Event_Summary dict.
        raw_event: Raw CloudTrail event detail dict.
    """
    source_arn = event_summary["identity_arn"]

    # Target role ARN is in requestParameters.roleArn
    request_params = raw_event.get("requestParameters") or {}
    target_arn = request_params.get("roleArn", "")
    if not target_arn:
        logger.warning("AssumeRole event missing roleArn in requestParameters",
                       extra={"event_id": event_summary.get("event_id")})
        return

    now = _utc_now()
    source_account = extract_account_id(source_arn)
    target_account = extract_account_id(target_arn)

    # Determine relationship type
    relationship_type = (
        "CrossAccount" if source_account != target_account else "AssumeRole"
    )

    update_item(
        table_name=table_name,
        key={"source_arn": source_arn, "target_arn": target_arn},
        update_expression=(
            "SET relationship_type = if_not_exists(relationship_type, :rt), "
            "discovery_timestamp = if_not_exists(discovery_timestamp, :now), "
            "source_account_id = if_not_exists(source_account_id, :sa), "
            "target_account_id = if_not_exists(target_account_id, :ta), "
            "is_active = :active, "
            "last_used_timestamp = :now"
        ),
        expression_attribute_values={
            ":rt": relationship_type,
            ":now": now,
            ":sa": source_account,
            ":ta": target_account,
            ":active": True,
        },
    )

    logger.info("Recorded trust relationship", extra={
        "source_arn": source_arn,
        "target_arn": target_arn,
        "relationship_type": relationship_type,
    })


def mark_identity_inactive(table_name: str, identity_arn: str) -> None:
    """Mark an identity as inactive on deletion events.

    Preserves the record for historical audit purposes.

    Args:
        table_name: Identity_Profile DynamoDB table name.
        identity_arn: Full identity ARN.
    """
    now = _utc_now()
    update_item(
        table_name=table_name,
        key={"identity_arn": identity_arn},
        update_expression="SET is_active = :inactive, last_activity_timestamp = :now",
        expression_attribute_values={":inactive": False, ":now": now},
    )
    logger.info("Marked identity inactive", extra={"identity_arn": identity_arn})
