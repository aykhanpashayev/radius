"""Incident processor lifecycle, SNS routing, and property tests for Radius.

Tests cover:
- Incident creation with all required fields
- Initial status and status_history invariants
- UUID v4 format validation
- Deduplication (append to existing incident)
- SNS alert routing by severity
- Status transitions
- Properties P7–P9
"""

import json
import re
import uuid
from typing import Any

import boto3
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.common.dynamodb_utils import get_item
from backend.common.errors import ValidationError
from backend.functions.incident_processor.processor import (
    append_event_to_incident,
    create_incident,
    find_duplicate,
    publish_alert,
    transition_status,
    validate_finding,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_HIGH_SEVERITIES = ("High", "Very High", "Critical")
_LOW_SEVERITIES = ("Low", "Moderate")
_ALL_SEVERITIES = _HIGH_SEVERITIES + _LOW_SEVERITIES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(
    identity_arn: str = "arn:aws:iam::111111111111:user/test-user",
    detection_type: str = "logging_disruption",
    severity: str = "Critical",
    confidence: int = 90,
    event_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "identity_arn": identity_arn,
        "detection_type": detection_type,
        "severity": severity,
        "confidence": confidence,
        "related_event_ids": event_ids or [str(uuid.uuid4())],
    }


def _subscribe_sqs_to_sns(sns_topic_arn: str) -> str:
    """Create an SQS queue, subscribe it to the SNS topic, return queue URL."""
    sqs = boto3.client("sqs", region_name="us-east-1")
    sns = boto3.client("sns", region_name="us-east-1")

    queue_resp = sqs.create_queue(QueueName="test-alert-queue")
    queue_url = queue_resp["QueueUrl"]

    queue_attrs = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )
    queue_arn = queue_attrs["Attributes"]["QueueArn"]

    sns.subscribe(TopicArn=sns_topic_arn, Protocol="sqs", Endpoint=queue_arn)
    return queue_url


def _drain_sqs(queue_url: str) -> list[dict]:
    """Receive all available messages from an SQS queue."""
    sqs = boto3.client("sqs", region_name="us-east-1")
    messages = []
    while True:
        resp = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=0
        )
        batch = resp.get("Messages", [])
        if not batch:
            break
        messages.extend(batch)
    return messages


# ---------------------------------------------------------------------------
# Task 12: Example-based tests
# ---------------------------------------------------------------------------

def test_incident_created_with_all_required_fields(dynamodb_tables, sns_topic):
    """create_incident writes a record with all 11 required fields."""
    finding = _make_finding()
    incident = create_incident(dynamodb_tables["incident"], finding)

    record = get_item(dynamodb_tables["incident"], {"incident_id": incident["incident_id"]})
    assert record is not None

    required = {
        "incident_id", "identity_arn", "detection_type", "severity",
        "confidence", "status", "creation_timestamp", "update_timestamp",
        "related_event_ids", "status_history", "notes",
    }
    missing = required - set(record.keys())
    assert not missing, f"Missing fields: {missing}"


def test_initial_status_is_open(dynamodb_tables, sns_topic):
    """Newly created incident has status == 'open'."""
    incident = create_incident(dynamodb_tables["incident"], _make_finding())
    record = get_item(dynamodb_tables["incident"], {"incident_id": incident["incident_id"]})
    assert record["status"] == "open"


def test_initial_status_history_has_one_entry(dynamodb_tables, sns_topic):
    """Newly created incident has exactly 1 status_history entry with status 'open'."""
    incident = create_incident(dynamodb_tables["incident"], _make_finding())
    record = get_item(dynamodb_tables["incident"], {"incident_id": incident["incident_id"]})
    assert len(record["status_history"]) == 1
    assert record["status_history"][0]["status"] == "open"


def test_incident_id_is_valid_uuid4(dynamodb_tables, sns_topic):
    """incident_id matches UUID v4 format."""
    incident = create_incident(dynamodb_tables["incident"], _make_finding())
    assert _UUID4_RE.match(incident["incident_id"]), (
        f"incident_id {incident['incident_id']!r} is not a valid UUID v4"
    )


def test_duplicate_finding_appends_to_existing_incident(dynamodb_tables, sns_topic):
    """find_duplicate + append_event_to_incident keeps exactly 1 record and updates event IDs."""
    finding = _make_finding(event_ids=["event-001"])
    incident = create_incident(dynamodb_tables["incident"], finding)
    incident_id = incident["incident_id"]

    # Second finding — same identity + detection_type
    duplicate = find_duplicate(
        dynamodb_tables["incident"],
        finding["identity_arn"],
        finding["detection_type"],
    )
    assert duplicate is not None, "find_duplicate should return the existing incident"
    assert duplicate["incident_id"] == incident_id

    append_event_to_incident(dynamodb_tables["incident"], incident_id, ["event-002"])

    record = get_item(dynamodb_tables["incident"], {"incident_id": incident_id})
    assert "event-001" in record["related_event_ids"]
    assert "event-002" in record["related_event_ids"]

    # Confirm still only 1 record in the table
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(dynamodb_tables["incident"])
    scan = table.scan(
        FilterExpression=(
            boto3.dynamodb.conditions.Attr("identity_arn").eq(finding["identity_arn"])
            & boto3.dynamodb.conditions.Attr("detection_type").eq(finding["detection_type"])
        )
    )
    assert len(scan["Items"]) == 1


def test_high_severity_publishes_sns_alert(dynamodb_tables, sns_topic):
    """publish_alert sends an SNS message for severity == 'High'."""
    queue_url = _subscribe_sqs_to_sns(sns_topic)
    incident = create_incident(dynamodb_tables["incident"], _make_finding(severity="High"))
    publish_alert(sns_topic, incident)
    messages = _drain_sqs(queue_url)
    assert len(messages) == 1


def test_very_high_severity_publishes_sns_alert(dynamodb_tables, sns_topic):
    """publish_alert sends an SNS message for severity == 'Very High'."""
    queue_url = _subscribe_sqs_to_sns(sns_topic)
    incident = create_incident(dynamodb_tables["incident"], _make_finding(severity="Very High"))
    publish_alert(sns_topic, incident)
    messages = _drain_sqs(queue_url)
    assert len(messages) == 1


def test_critical_severity_publishes_sns_alert(dynamodb_tables, sns_topic):
    """publish_alert sends an SNS message for severity == 'Critical'."""
    queue_url = _subscribe_sqs_to_sns(sns_topic)
    incident = create_incident(dynamodb_tables["incident"], _make_finding(severity="Critical"))
    publish_alert(sns_topic, incident)
    messages = _drain_sqs(queue_url)
    assert len(messages) == 1


def test_low_severity_does_not_publish_sns_alert(dynamodb_tables, sns_topic):
    """publish_alert sends no SNS message for severity == 'Low'."""
    queue_url = _subscribe_sqs_to_sns(sns_topic)
    incident = create_incident(dynamodb_tables["incident"], _make_finding(severity="Low"))
    publish_alert(sns_topic, incident)
    messages = _drain_sqs(queue_url)
    assert len(messages) == 0


def test_moderate_severity_does_not_publish_sns_alert(dynamodb_tables, sns_topic):
    """publish_alert sends no SNS message for severity == 'Moderate'."""
    queue_url = _subscribe_sqs_to_sns(sns_topic)
    incident = create_incident(dynamodb_tables["incident"], _make_finding(severity="Moderate"))
    publish_alert(sns_topic, incident)
    messages = _drain_sqs(queue_url)
    assert len(messages) == 0


def test_status_transition_open_to_investigating(dynamodb_tables, sns_topic):
    """transition_status open→investigating updates status, status_history, and update_timestamp."""
    incident = create_incident(dynamodb_tables["incident"], _make_finding())
    incident_id = incident["incident_id"]
    original_update_ts = incident["update_timestamp"]

    transition_status(dynamodb_tables["incident"], incident_id, "open", "investigating")

    record = get_item(dynamodb_tables["incident"], {"incident_id": incident_id})
    assert record["status"] == "investigating"
    assert len(record["status_history"]) == 2
    assert record["status_history"][1]["status"] == "investigating"
    assert record["update_timestamp"] >= original_update_ts


# ---------------------------------------------------------------------------
# Task 13: Property tests P7–P9
# ---------------------------------------------------------------------------

def _valid_finding_strategy():
    """Hypothesis strategy generating valid finding dicts."""
    return st.fixed_dictionaries({
        "identity_arn": st.from_regex(
            r"arn:aws:iam::\d{12}:user/[a-zA-Z0-9_\-]+", fullmatch=True
        ),
        "detection_type": st.sampled_from([
            "privilege_escalation",
            "cross_account_role_assumption",
            "logging_disruption",
            "root_user_activity",
            "api_burst_anomaly",
            "iam_policy_modification_spike",
            "unusual_service_usage",
        ]),
        "severity": st.sampled_from(list(_ALL_SEVERITIES)),
        "confidence": st.integers(min_value=0, max_value=100),
        "related_event_ids": st.lists(
            st.uuids().map(str), min_size=1, max_size=5
        ),
    })


@given(finding=_valid_finding_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_incident_structure_invariant(finding, dynamodb_tables, sns_topic):
    # Feature: phase-6-testing-and-documentation, Property 7: Incident structure invariant
    """For any valid Finding, the created Incident has all required fields,
    a valid UUID v4 incident_id, status == 'open', and len(status_history) == 1."""
    incident = create_incident(dynamodb_tables["incident"], finding)
    record = get_item(dynamodb_tables["incident"], {"incident_id": incident["incident_id"]})

    assert record is not None
    required = {
        "incident_id", "identity_arn", "detection_type", "severity",
        "confidence", "status", "creation_timestamp", "update_timestamp",
        "related_event_ids", "status_history", "notes",
    }
    assert not (required - set(record.keys())), f"Missing fields: {required - set(record.keys())}"
    assert _UUID4_RE.match(record["incident_id"])
    assert record["status"] == "open"
    assert len(record["status_history"]) == 1


@given(
    identity_arn=st.from_regex(
        r"arn:aws:iam::\d{12}:user/[a-zA-Z0-9_\-]+", fullmatch=True
    ),
    detection_type=st.sampled_from([
        "privilege_escalation",
        "logging_disruption",
        "root_user_activity",
        "api_burst_anomaly",
    ]),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_deduplication_invariant(identity_arn, detection_type, dynamodb_tables, sns_topic):
    # Feature: phase-6-testing-and-documentation, Property 8: Deduplication invariant
    """For any (identity_arn, detection_type) pair, two Findings within 24 hours
    produce exactly 1 Incident record in DynamoDB."""
    finding1 = _make_finding(
        identity_arn=identity_arn,
        detection_type=detection_type,
        event_ids=[str(uuid.uuid4())],
    )
    finding2 = _make_finding(
        identity_arn=identity_arn,
        detection_type=detection_type,
        event_ids=[str(uuid.uuid4())],
    )

    # First finding — creates incident
    incident = create_incident(dynamodb_tables["incident"], finding1)

    # Second finding — should deduplicate
    duplicate = find_duplicate(dynamodb_tables["incident"], identity_arn, detection_type)
    if duplicate:
        append_event_to_incident(
            dynamodb_tables["incident"],
            duplicate["incident_id"],
            finding2["related_event_ids"],
        )
    else:
        create_incident(dynamodb_tables["incident"], finding2)

    # Exactly 1 record for this identity + detection_type
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(dynamodb_tables["incident"])
    scan = table.scan(
        FilterExpression=(
            boto3.dynamodb.conditions.Attr("identity_arn").eq(identity_arn)
            & boto3.dynamodb.conditions.Attr("detection_type").eq(detection_type)
        )
    )
    assert len(scan["Items"]) == 1, (
        f"Expected 1 incident, got {len(scan['Items'])} for "
        f"{identity_arn} / {detection_type}"
    )


@given(severity=st.sampled_from(list(_ALL_SEVERITIES)))
@settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_sns_alert_routing(severity, dynamodb_tables, sns_topic):
    # Feature: phase-6-testing-and-documentation, Property 9: SNS alert routing
    """publish_alert publishes to SNS iff severity is High, Very High, or Critical.
    Low and Moderate severities produce zero SNS messages."""
    queue_url = _subscribe_sqs_to_sns(sns_topic)
    incident = create_incident(
        dynamodb_tables["incident"], _make_finding(severity=severity)
    )
    publish_alert(sns_topic, incident)
    messages = _drain_sqs(queue_url)

    if severity in _HIGH_SEVERITIES:
        assert len(messages) == 1, f"Expected 1 SNS message for severity={severity!r}"
    else:
        assert len(messages) == 0, f"Expected 0 SNS messages for severity={severity!r}"
