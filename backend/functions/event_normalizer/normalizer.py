"""CloudTrail event parsing and normalization logic for Event_Normalizer."""

import json
import re
from datetime import datetime, timezone
from typing import Any

from dateutil import parser as dateutil_parser

from backend.common.errors import EventProcessingError, ValidationError
from backend.common.logging_utils import get_logger
from backend.common.validation import (
    sanitize_event_data,
    validate_required_fields,
    validate_timestamp,
)

logger = get_logger(__name__)

# ARN extraction from userIdentity
_ARN_FIELDS = ("arn", "principalId")

# Identity type mapping from CloudTrail userIdentity.type
_IDENTITY_TYPE_MAP = {
    "IAMUser": "IAMUser",
    "AssumedRole": "AssumedRole",
    "Role": "AssumedRole",
    "AWSService": "AWSService",
    "AWSAccount": "AWSService",
    "FederatedUser": "AssumedRole",
    "Root": "IAMUser",
}


def extract_identity_arn(user_identity: dict[str, Any]) -> str:
    """Extract and normalize the identity ARN from userIdentity.

    Args:
        user_identity: CloudTrail userIdentity dict.

    Returns:
        Normalized identity ARN string.

    Raises:
        ValidationError: If no usable ARN can be extracted.
    """
    # Prefer explicit ARN
    arn = user_identity.get("arn")
    if arn:
        # For AssumedRole, strip the session suffix to get the role ARN
        # e.g. arn:aws:sts::123:assumed-role/MyRole/session → arn:aws:iam::123:role/MyRole
        if "assumed-role" in arn:
            match = re.match(
                r"arn:([^:]+):sts::(\d+):assumed-role/([^/]+)/.*", arn
            )
            if match:
                partition, account_id, role_name = match.groups()
                return f"arn:{partition}:iam::{account_id}:role/{role_name}"
        return arn

    # Fall back to principalId for service principals
    principal_id = user_identity.get("principalId", "")
    identity_type = user_identity.get("type", "")
    account_id = user_identity.get("accountId", "")

    if identity_type == "AWSService":
        service = user_identity.get("invokedBy", principal_id)
        return f"arn:aws:iam::{account_id}:service/{service}"

    raise ValidationError(
        f"Cannot extract ARN from userIdentity type={identity_type!r}"
    )


def normalize_timestamp(raw_ts: str) -> str:
    """Parse any timestamp format and return ISO 8601 UTC with microseconds.

    Args:
        raw_ts: Raw timestamp string from CloudTrail.

    Returns:
        ISO 8601 UTC timestamp string.

    Raises:
        ValidationError: If the timestamp cannot be parsed.
    """
    try:
        dt = dateutil_parser.parse(raw_ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError) as exc:
        raise ValidationError(f"Cannot parse timestamp {raw_ts!r}: {exc}") from exc


def parse_cloudtrail_event(raw_event: dict[str, Any]) -> dict[str, Any]:
    """Parse a raw CloudTrail event into a normalized Event_Summary record.

    Args:
        raw_event: Raw CloudTrail event dict from EventBridge.

    Returns:
        Normalized Event_Summary dict ready for DynamoDB storage.

    Raises:
        ValidationError: If required fields are missing or malformed.
        EventProcessingError: If the event cannot be processed.
    """
    # EventBridge wraps CloudTrail events under 'detail'
    detail = raw_event.get("detail", raw_event)

    validate_required_fields(detail)

    user_identity = detail["userIdentity"]
    identity_arn = extract_identity_arn(user_identity)
    timestamp = normalize_timestamp(detail["eventTime"])
    date_partition = timestamp[:10]  # YYYY-MM-DD

    # Extract account ID from ARN or detail
    account_id = (
        detail.get("recipientAccountId")
        or detail.get("userIdentity", {}).get("accountId")
        or _extract_account_from_arn(identity_arn)
        or "unknown"
    )

    # Build sanitized event parameters (exclude sensitive data, enforce 10KB limit)
    raw_params = {
        "requestParameters": detail.get("requestParameters"),
        "responseElements": detail.get("responseElements"),
        "resources": detail.get("resources"),
    }
    sanitized_params = sanitize_event_data(raw_params)

    event_name = detail.get("eventName", "")
    event_source = detail.get("eventSource", "")
    # Build event_type as "service:EventName" so detection rules can extract
    # the service prefix for prior_services_30d context (e.g. "iam:AttachUserPolicy")
    if event_source and "." in event_source:
        service_prefix = event_source.split(".")[0].lower()
        event_type = f"{service_prefix}:{event_name}"
    else:
        event_type = event_name

    event_summary = {
        "identity_arn": identity_arn,
        "timestamp": timestamp,
        "event_id": detail.get("eventID", ""),
        "event_type": event_type,
        "event_name": event_name,
        "source_ip": detail.get("sourceIPAddress", ""),
        "user_agent": detail.get("userAgent", ""),
        "event_parameters": sanitized_params,
        "date_partition": date_partition,
        "account_id": account_id,
        "region": detail.get("awsRegion", ""),
    }

    return event_summary


def _extract_account_from_arn(arn: str) -> str | None:
    """Extract account ID from an ARN string."""
    parts = arn.split(":")
    if len(parts) >= 5:
        account = parts[4]
        return account if account.isdigit() else None
    return None
