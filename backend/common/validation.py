"""Input validation utilities for Radius Lambda functions."""

import re
import sys
from datetime import datetime, timezone
from typing import Any

from backend.common.errors import ValidationError

# ARN pattern: arn:partition:service:region:account-id:resource
_ARN_RE = re.compile(
    r"^arn:[a-z0-9\-]+:[a-z0-9\-]+:[a-z0-9\-]*:[0-9]{0,12}:.+$"
)

# ISO 8601 with optional fractional seconds and timezone
_ISO8601_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

# Fields that may contain sensitive data and should be excluded
_SENSITIVE_FIELD_PATTERNS = re.compile(
    r"(password|secret|token|key|credential|auth|private|ssn|credit)",
    re.IGNORECASE,
)

# Required top-level fields in a CloudTrail event
_REQUIRED_CLOUDTRAIL_FIELDS = {"eventName", "userIdentity", "eventTime"}

# Maximum allowed size for event_parameters payload (bytes)
_MAX_PAYLOAD_BYTES = 10 * 1024  # 10 KB


def validate_arn(arn: str) -> str:
    """Validate and return an ARN string.

    Args:
        arn: ARN string to validate.

    Returns:
        The validated ARN.

    Raises:
        ValidationError: If the ARN format is invalid.
    """
    if not isinstance(arn, str) or not _ARN_RE.match(arn):
        raise ValidationError(f"Invalid ARN format: {arn!r}")
    return arn


def validate_timestamp(ts: str) -> str:
    """Validate an ISO 8601 timestamp string.

    Args:
        ts: Timestamp string to validate.

    Returns:
        The validated timestamp.

    Raises:
        ValidationError: If the timestamp format is invalid.
    """
    if not isinstance(ts, str) or not _ISO8601_RE.match(ts):
        raise ValidationError(f"Invalid ISO 8601 timestamp: {ts!r}")
    return ts


def validate_required_fields(event: dict[str, Any]) -> None:
    """Validate that a CloudTrail event contains all required fields.

    Args:
        event: CloudTrail event dict.

    Raises:
        ValidationError: If any required field is missing.
    """
    missing = _REQUIRED_CLOUDTRAIL_FIELDS - set(event.keys())
    if missing:
        raise ValidationError(f"CloudTrail event missing required fields: {sorted(missing)}")

    # userIdentity must have a type
    user_identity = event.get("userIdentity", {})
    if not isinstance(user_identity, dict) or not user_identity.get("type"):
        raise ValidationError("CloudTrail event userIdentity missing 'type' field")


def sanitize_event_data(event: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy of a CloudTrail event.

    Removes sensitive fields and truncates large payloads.

    Args:
        event: Raw CloudTrail event dict.

    Returns:
        Sanitized event dict safe for storage.
    """
    sanitized = _redact_sensitive(event)

    # Enforce 10 KB limit on the full payload
    import json
    encoded = json.dumps(sanitized, default=str)
    if len(encoded.encode()) > _MAX_PAYLOAD_BYTES:
        # Keep only the essential fields
        sanitized = {
            "eventId": sanitized.get("eventID"),
            "eventName": sanitized.get("eventName"),
            "eventTime": sanitized.get("eventTime"),
            "userIdentity": sanitized.get("userIdentity"),
            "sourceIPAddress": sanitized.get("sourceIPAddress"),
            "userAgent": sanitized.get("userAgent"),
            "_truncated": True,
        }

    return sanitized


def _redact_sensitive(obj: Any) -> Any:
    """Recursively redact sensitive keys from a dict/list structure."""
    if isinstance(obj, dict):
        return {
            k: "[REDACTED]" if _SENSITIVE_FIELD_PATTERNS.search(k) else _redact_sensitive(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_redact_sensitive(item) for item in obj]
    return obj
