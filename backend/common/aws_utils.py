"""Shared AWS utility functions for Radius backend."""
from __future__ import annotations


def extract_account_id(arn: str) -> str:
    """Extract AWS account ID from an ARN.

    Args:
        arn: Full ARN string (e.g. arn:aws:iam::123456789012:user/alice).

    Returns:
        12-digit account ID string, or empty string if not found.
    """
    parts = arn.split(":")
    if len(parts) >= 5 and parts[4].isdigit():
        return parts[4]
    return ""


def extract_event_name(event_type: str) -> str:
    """Extract the action name from a CloudTrail event_type string.

    CloudTrail event_type is formatted as "service:ActionName"
    (e.g. "iam:CreateUser" -> "CreateUser", "sts:AssumeRole" -> "AssumeRole").
    If no colon is present, returns the full string unchanged.

    Args:
        event_type: The event_type field from an Event_Summary record.

    Returns:
        The action name portion of the event type.
    """
    return event_type.split(":")[-1] if ":" in event_type else event_type
