"""Attack scenario simulation tests for Radius.

Tests the full pipeline end-to-end for each of the 5 attack scenarios
defined in the design document, plus deduplication.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
import pytest

from backend.common.dynamodb_utils import get_item, put_item
from backend.functions.incident_processor.processor import (
    append_event_to_incident,
    create_incident,
    find_duplicate,
)

from backend.tests.integration.test_pipeline_e2e import (
    _make_cloudtrail_event,
    _run_normalizer,
    _run_collector,
    _run_detection,
    _run_incident_processor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_event_summary(
    identity_arn: str,
    event_type: str,
    event_parameters: dict | None = None,
) -> dict[str, Any]:
    """Build a minimal event_summary dict bypassing the normalizer."""
    return {
        "identity_arn": identity_arn,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "date_partition": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "account_id": identity_arn.split(":")[4] if len(identity_arn.split(":")) > 4 else "111111111111",
        "source_ip": "203.0.113.1",
        "user_agent": "aws-cli/2.15.0",
        "event_parameters": event_parameters or {},
        "region": "us-east-1",
    }


def _process_event(raw_event: dict, tables: dict, sns_topic_arn: str) -> list[dict]:
    """Run a raw event through the full pipeline and return created/updated incidents."""
    event_summary = _run_normalizer(raw_event)
    put_item(tables["event_summary"], event_summary)
    _run_collector(event_summary, raw_event, tables)
    findings = _run_detection(event_summary, tables)
    incidents = []
    for finding in findings:
        finding_dict = {
            "identity_arn": finding.identity_arn,
            "detection_type": finding.detection_type,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "related_event_ids": finding.related_event_ids,
        }
        incident, _ = _run_incident_processor(finding_dict, tables, sns_topic_arn)
        incidents.append(incident)
    return incidents


def _process_event_summary(event_summary: dict, tables: dict, sns_topic_arn: str) -> list[dict]:
    """Run a pre-built event_summary through detection + incident processor."""
    put_item(tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, tables)
    incidents = []
    for finding in findings:
        finding_dict = {
            "identity_arn": finding.identity_arn,
            "detection_type": finding.detection_type,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "related_event_ids": finding.related_event_ids,
        }
        incident, _ = _run_incident_processor(finding_dict, tables, sns_topic_arn)
        incidents.append(incident)
    return incidents


# ---------------------------------------------------------------------------
# Scenario 1: Privilege Escalation
# ---------------------------------------------------------------------------

def test_privilege_escalation_scenario(dynamodb_tables, sns_topic):
    """CreateUser followed by AttachUserPolicy triggers privilege_escalation incident."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"
    account_id = "111111111111"

    # T+0: CreateUser — write to Event_Summary so it appears in recent_events_60m
    create_event = _make_cloudtrail_event("CreateUser", identity_arn, account_id)
    create_summary = _run_normalizer(create_event)
    put_item(dynamodb_tables["event_summary"], create_summary)
    _run_collector(create_summary, create_event, dynamodb_tables)

    # T+5m: AttachUserPolicy — triggers privilege_escalation (CreateUser in recent_events_60m)
    attach_event = _make_cloudtrail_event("AttachUserPolicy", identity_arn, account_id)
    incidents = _process_event(attach_event, dynamodb_tables, sns_topic)

    assert any(i["detection_type"] == "privilege_escalation" for i in incidents), (
        f"Expected privilege_escalation incident, got: {[i['detection_type'] for i in incidents]}"
    )


# ---------------------------------------------------------------------------
# Scenario 2: Cross-Account Lateral Movement
# ---------------------------------------------------------------------------

def test_cross_account_lateral_movement_scenario(dynamodb_tables, sns_topic):
    """AssumeRole to a different account triggers cross_account_role_assumption incident."""
    identity_arn = "arn:aws:iam::111111111111:user/dev-user"
    target_role_arn = "arn:aws:iam::987654321098:role/OrganizationAccountAccessRole"

    # Build event_summary directly — rule reads event_parameters["roleArn"]
    event_summary = _build_event_summary(
        identity_arn=identity_arn,
        event_type="AssumeRole",
        event_parameters={"roleArn": target_role_arn},
    )
    incidents = _process_event_summary(event_summary, dynamodb_tables, sns_topic)

    assert any(i["detection_type"] == "cross_account_role_assumption" for i in incidents), (
        f"Expected cross_account_role_assumption incident, got: {[i['detection_type'] for i in incidents]}"
    )


# ---------------------------------------------------------------------------
# Scenario 3: Logging Disruption
# ---------------------------------------------------------------------------

def test_logging_disruption_scenario(dynamodb_tables, sns_topic):
    """StopLogging triggers logging_disruption incident with Critical severity."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"
    account_id = "111111111111"

    raw_event = _make_cloudtrail_event("StopLogging", identity_arn, account_id)
    incidents = _process_event(raw_event, dynamodb_tables, sns_topic)

    disruption_incidents = [i for i in incidents if i["detection_type"] == "logging_disruption"]
    assert disruption_incidents, "Expected logging_disruption incident"
    assert disruption_incidents[0]["severity"] == "Critical"


# ---------------------------------------------------------------------------
# Scenario 4: API Burst
# ---------------------------------------------------------------------------

def test_api_burst_scenario(dynamodb_tables, sns_topic):
    """20 DescribeInstances events within 5 minutes triggers api_burst_anomaly incident."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"
    account_id = "111111111111"

    # Use a fixed timestamp 1 minute ago so all events are guaranteed within the
    # 5-minute window regardless of how long the test suite takes to reach this test.
    event_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()

    # Write all 20 events to DynamoDB first so DetectionContext.build() sees all 20
    raw_events = []
    for _ in range(20):
        raw_event = _make_cloudtrail_event(
            "DescribeInstances", identity_arn, account_id, event_time=event_time
        )
        event_summary = _run_normalizer(raw_event)
        # Each event needs a unique event_id (sort key is timestamp, so override event_id too)
        event_summary["event_id"] = str(uuid.uuid4())
        event_summary["timestamp"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1, microseconds=len(raw_events))
        ).isoformat(timespec="microseconds")
        put_item(dynamodb_tables["event_summary"], event_summary)
        raw_events.append((raw_event, event_summary))

    # Run detection on the last event — context will see all 20 in recent_events_5m
    last_raw, last_summary = raw_events[-1]
    _run_collector(last_summary, last_raw, dynamodb_tables)
    findings = _run_detection(last_summary, dynamodb_tables)
    incidents = []
    for finding in findings:
        finding_dict = {
            "identity_arn": finding.identity_arn,
            "detection_type": finding.detection_type,
            "severity": finding.severity,
            "confidence": finding.confidence,
            "related_event_ids": finding.related_event_ids,
        }
        incident, _ = _run_incident_processor(finding_dict, dynamodb_tables, sns_topic)
        incidents.append(incident)

    burst_incidents = [i for i in incidents if i["detection_type"] == "api_burst_anomaly"]
    assert burst_incidents, (
        f"Expected api_burst_anomaly incident, got: {[i['detection_type'] for i in incidents]}"
    )


# ---------------------------------------------------------------------------
# Scenario 5: Root User Activity
# ---------------------------------------------------------------------------

def test_root_user_activity_scenario(dynamodb_tables, sns_topic):
    """Event from root ARN triggers root_user_activity incident with Very High severity."""
    identity_arn = "arn:aws:iam::111111111111:root"

    # Build event_summary directly — normalizer would transform the root ARN
    event_summary = _build_event_summary(identity_arn=identity_arn, event_type="CreateUser")
    incidents = _process_event_summary(event_summary, dynamodb_tables, sns_topic)

    root_incidents = [i for i in incidents if i["detection_type"] == "root_user_activity"]
    assert root_incidents, "Expected root_user_activity incident"
    assert root_incidents[0]["severity"] == "Very High"


# ---------------------------------------------------------------------------
# Scenario 6: Deduplication (Task 11)
# ---------------------------------------------------------------------------

def test_deduplication_prevents_duplicate_incident(dynamodb_tables, sns_topic):
    """Two StopLogging events for the same identity produce exactly 1 Incident record."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"
    account_id = "111111111111"

    # First StopLogging — creates incident
    raw_event_1 = _make_cloudtrail_event("StopLogging", identity_arn, account_id)
    incidents_1 = _process_event(raw_event_1, dynamodb_tables, sns_topic)
    disruption_1 = [i for i in incidents_1 if i["detection_type"] == "logging_disruption"]
    assert disruption_1, "First StopLogging should create a logging_disruption incident"
    first_incident_id = disruption_1[0]["incident_id"]

    # Second StopLogging — should append to existing incident, not create a new one
    raw_event_2 = _make_cloudtrail_event("StopLogging", identity_arn, account_id)
    _process_event(raw_event_2, dynamodb_tables, sns_topic)

    # Scan Incident table — should have exactly 1 record for this identity + detection_type
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(dynamodb_tables["incident"])
    response = table.scan(
        FilterExpression=(
            boto3.dynamodb.conditions.Attr("identity_arn").eq(identity_arn)
            & boto3.dynamodb.conditions.Attr("detection_type").eq("logging_disruption")
        )
    )
    items = response["Items"]
    assert len(items) == 1, f"Expected 1 incident record, got {len(items)}"

    # The single record should have both event IDs in related_event_ids
    incident_record = get_item(
        dynamodb_tables["incident"],
        {"incident_id": first_incident_id},
    )
    assert incident_record is not None
    assert len(incident_record["related_event_ids"]) >= 2, (
        f"Expected at least 2 related_event_ids after deduplication, "
        f"got: {incident_record['related_event_ids']}"
    )
