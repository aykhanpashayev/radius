"""Incident creation, deduplication, and status management for Incident_Processor."""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key, Attr

from backend.common.dynamodb_utils import get_dynamodb_client, put_item, update_item
from backend.common.errors import ValidationError
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

_REQUIRED_FIELDS = {"identity_arn", "detection_type", "severity"}
_HIGH_SEVERITY_LEVELS = {"High", "Very High", "Critical"}
_VALID_STATUSES = {"open", "investigating", "resolved", "false_positive"}
_VALID_TRANSITIONS = {
    "open": {"investigating", "false_positive"},
    "investigating": {"resolved", "false_positive"},
    "resolved": set(),
    "false_positive": set(),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def validate_finding(finding: dict[str, Any]) -> None:
    """Validate required fields on an incoming finding.

    Raises:
        ValidationError: If any required field is missing.
    """
    missing = _REQUIRED_FIELDS - set(finding.keys())
    if missing:
        raise ValidationError(f"Finding missing required fields: {sorted(missing)}")


def find_duplicate(
    table_name: str,
    identity_arn: str,
    detection_type: str,
) -> dict[str, Any] | None:
    """Query IdentityIndex GSI for a recent duplicate incident.

    Looks for an open/investigating incident with the same identity_arn
    and detection_type created within the last 24 hours.

    Args:
        table_name: Incident DynamoDB table name.
        identity_arn: Identity ARN to check.
        detection_type: Detection type to match.

    Returns:
        Existing incident dict or None.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    response = table.query(
        IndexName="IdentityIndex",
        KeyConditionExpression=(
            Key("identity_arn").eq(identity_arn)
            & Key("creation_timestamp").gte(cutoff)
        ),
        FilterExpression=(
            Attr("detection_type").eq(detection_type)
            & Attr("status").is_in(["open", "investigating"])
        ),
    )

    items = response.get("Items", [])
    return items[0] if items else None


def create_incident(
    table_name: str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    """Create a new Incident record in DynamoDB.

    Args:
        table_name: Incident DynamoDB table name.
        finding: Validated finding dict.

    Returns:
        Created incident dict.
    """
    now = _utc_now()
    incident_id = str(uuid.uuid4())

    incident = {
        "incident_id": incident_id,
        "identity_arn": finding["identity_arn"],
        "detection_type": finding["detection_type"],
        "severity": finding["severity"],
        "confidence": finding.get("confidence", 0),
        "status": "open",
        "creation_timestamp": now,
        "update_timestamp": now,
        "related_event_ids": finding.get("related_event_ids", []),
        "status_history": [{"status": "open", "timestamp": now}],
        "notes": "",
        "assigned_to": "",
    }

    put_item(table_name, incident)
    logger.info("Created incident", extra={
        "incident_id": incident_id,
        "identity_arn": finding["identity_arn"],
        "severity": finding["severity"],
    })
    return incident


def append_event_to_incident(
    table_name: str,
    incident_id: str,
    new_event_ids: list[str],
) -> None:
    """Append new event IDs to an existing incident (deduplication path).

    Args:
        table_name: Incident DynamoDB table name.
        incident_id: Existing incident ID.
        new_event_ids: Event IDs to append.
    """
    now = _utc_now()
    update_item(
        table_name=table_name,
        key={"incident_id": incident_id},
        update_expression=(
            "SET update_timestamp = :now, "
            "related_event_ids = list_append(if_not_exists(related_event_ids, :empty), :new_ids)"
        ),
        expression_attribute_values={
            ":now": now,
            ":new_ids": new_event_ids,
            ":empty": [],
        },
    )
    logger.info("Appended events to existing incident", extra={
        "incident_id": incident_id,
        "new_event_count": len(new_event_ids),
    })


def transition_status(
    table_name: str,
    incident_id: str,
    current_status: str,
    new_status: str,
) -> dict[str, Any]:
    """Transition an incident to a new status.

    Args:
        table_name: Incident DynamoDB table name.
        incident_id: Incident ID.
        current_status: Current status (for validation).
        new_status: Target status.

    Returns:
        Updated incident attributes.

    Raises:
        ValidationError: If the transition is not allowed.
    """
    if new_status not in _VALID_STATUSES:
        raise ValidationError(f"Invalid status: {new_status!r}")

    allowed = _VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Invalid transition {current_status!r} → {new_status!r}. "
            f"Allowed: {sorted(allowed)}"
        )

    now = _utc_now()
    return update_item(
        table_name=table_name,
        key={"incident_id": incident_id},
        update_expression=(
            "SET #st = :new_status, "
            "update_timestamp = :now, "
            "status_history = list_append(if_not_exists(status_history, :empty), :entry)"
        ),
        expression_attribute_values={
            ":new_status": new_status,
            ":now": now,
            ":entry": [{"status": new_status, "timestamp": now}],
            ":empty": [],
        },
        expression_attribute_names={"#st": "status"},
    )


def publish_alert(
    sns_topic_arn: str,
    incident: dict[str, Any],
) -> None:
    """Publish an SNS alert for high-severity incidents.

    Args:
        sns_topic_arn: Alert_Topic ARN.
        incident: Incident dict to alert on.
    """
    severity = incident.get("severity", "")
    if severity not in _HIGH_SEVERITY_LEVELS:
        return

    sns = boto3.client("sns")
    subject = f"[{severity}] Radius Security Incident: {incident.get('detection_type', '')}"
    message = json.dumps({
        "incident_id": incident["incident_id"],
        "identity_arn": incident["identity_arn"],
        "detection_type": incident["detection_type"],
        "severity": severity,
        "confidence": incident.get("confidence", 0),
        "creation_timestamp": incident["creation_timestamp"],
        "dashboard_link": f"https://radius.internal/incidents/{incident['incident_id']}",
    }, indent=2)

    sns.publish(
        TopicArn=sns_topic_arn,
        Subject=subject,
        Message=message,
        MessageAttributes={
            "severity": {"DataType": "String", "StringValue": severity}
        },
    )
    logger.info("Published SNS alert", extra={
        "incident_id": incident["incident_id"],
        "severity": severity,
    })
