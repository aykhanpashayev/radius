"""Detection rule accuracy integration tests for Radius.

Tests that each detection rule fires correctly on known-triggering events
and stays silent on benign events. Uses moto-mocked DynamoDB via conftest.py.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.common.dynamodb_utils import put_item
from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.engine import RuleEngine
from backend.functions.detection_engine.interfaces import Finding

from backend.tests.integration.test_pipeline_e2e import (
    _make_cloudtrail_event,
    _run_normalizer,
    _run_detection,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_DIR = Path(__file__).parent.parent.parent.parent / "sample-data" / "cloud-trail-events"


def _load_sample(filename: str) -> dict[str, Any]:
    """Load a sample CloudTrail event from sample-data/cloud-trail-events/."""
    return json.loads((_SAMPLE_DIR / filename).read_text())


def _build_event_summary(
    identity_arn: str,
    event_type: str,
    event_parameters: dict | None = None,
    identity_type: str = "",
) -> dict[str, Any]:
    """Build a minimal event_summary dict for direct rule evaluation (bypassing normalizer)."""
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
        "identity_type": identity_type,
    }


def _empty_context(identity_arn: str) -> DetectionContext:
    """Build an empty DetectionContext (no historical events)."""
    return DetectionContext(identity_arn=identity_arn)


# ---------------------------------------------------------------------------
# Example-based tests
# ---------------------------------------------------------------------------

def test_privilege_escalation_fires_on_sample_event(dynamodb_tables):
    """AttachUserPolicy sample event fires privilege_escalation when CreateUser is in recent history."""
    raw_event = _load_sample("suspicious-privilege-escalation.json")
    identity_arn = raw_event["userIdentity"]["arn"]

    # Write a CreateUser event to Event_Summary so the context-aware rule fires
    create_user_summary = _build_event_summary(identity_arn, "CreateUser")
    put_item(dynamodb_tables["event_summary"], create_user_summary)

    # Normalize and run detection — override timestamp to now so it falls within recent_events_60m
    event_summary = _run_normalizer(raw_event)
    event_summary["timestamp"] = datetime.now(timezone.utc).isoformat()
    put_item(dynamodb_tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, dynamodb_tables)

    assert any(f.detection_type == "privilege_escalation" for f in findings), (
        f"Expected privilege_escalation finding, got: {[f.detection_type for f in findings]}"
    )


def test_cross_account_role_assumption_fires_on_sample_event(dynamodb_tables):
    """AssumeRole targeting a different account fires cross_account_role_assumption."""
    identity_arn = "arn:aws:iam::123456789012:user/dev-user"
    target_role_arn = "arn:aws:iam::987654321098:role/OrganizationAccountAccessRole"

    # Build event_summary directly — rule reads event_parameters["roleArn"]
    event_summary = _build_event_summary(
        identity_arn=identity_arn,
        event_type="AssumeRole",
        event_parameters={"roleArn": target_role_arn},
    )
    put_item(dynamodb_tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, dynamodb_tables)

    assert any(f.detection_type == "cross_account_role_assumption" for f in findings), (
        f"Expected cross_account_role_assumption finding, got: {[f.detection_type for f in findings]}"
    )


def test_logging_disruption_fires_with_critical_severity(dynamodb_tables):
    """StopLogging event fires logging_disruption with Critical severity."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"
    raw_event = _make_cloudtrail_event("StopLogging", identity_arn, "111111111111")

    event_summary = _run_normalizer(raw_event)
    put_item(dynamodb_tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, dynamodb_tables)

    disruption_findings = [f for f in findings if f.detection_type == "logging_disruption"]
    assert disruption_findings, "Expected logging_disruption finding"
    assert disruption_findings[0].severity == "Critical"


def test_root_user_activity_fires_with_very_high_severity(dynamodb_tables):
    """Event from root ARN fires root_user_activity with Very High severity."""
    identity_arn = "arn:aws:iam::111111111111:root"

    # Build event_summary directly — normalizer would transform the ARN
    event_summary = _build_event_summary(
        identity_arn=identity_arn,
        event_type="CreateUser",
    )
    put_item(dynamodb_tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, dynamodb_tables)

    root_findings = [f for f in findings if f.detection_type == "root_user_activity"]
    assert root_findings, "Expected root_user_activity finding"
    assert root_findings[0].severity == "Very High"


def test_benign_list_users_produces_no_findings(dynamodb_tables):
    """ListUsers event with no suspicious context produces no findings."""
    identity_arn = "arn:aws:iam::111111111111:user/readonly-user"
    raw_event = _make_cloudtrail_event("ListUsers", identity_arn, "111111111111")

    event_summary = _run_normalizer(raw_event)
    put_item(dynamodb_tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, dynamodb_tables)

    assert findings == [], f"Expected no findings for ListUsers, got: {[f.detection_type for f in findings]}"


def test_finding_detection_type_matches_rule_id(dynamodb_tables):
    """For each triggering event, finding.detection_type equals the expected rule_id."""
    cases = [
        # (event_summary, expected_detection_type)
        (
            _build_event_summary("arn:aws:iam::111111111111:user/u", "StopLogging"),
            "logging_disruption",
        ),
        (
            _build_event_summary(
                "arn:aws:iam::111111111111:user/u",
                "AssumeRole",
                event_parameters={"roleArn": "arn:aws:iam::987654321098:role/R"},
            ),
            "cross_account_role_assumption",
        ),
        (
            _build_event_summary("arn:aws:iam::111111111111:root", "CreateUser"),
            "root_user_activity",
        ),
    ]

    for event_summary, expected_type in cases:
        put_item(dynamodb_tables["event_summary"], event_summary)
        findings = _run_detection(event_summary, dynamodb_tables)
        matched = [f for f in findings if f.detection_type == expected_type]
        assert matched, (
            f"Expected {expected_type} finding, got: {[f.detection_type for f in findings]}"
        )
        assert matched[0].detection_type == expected_type


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

@st.composite
def triggering_event_strategy(draw):
    """Generate (event_summary, expected_rule_id) pairs that trigger at least one detection rule."""
    rule_choice = draw(st.sampled_from(["logging_disruption", "cross_account_role_assumption", "root_user_activity"]))

    if rule_choice == "logging_disruption":
        identity_arn = draw(st.from_regex(
            r"arn:aws:iam::[0-9]{12}:(user|role)/[a-zA-Z0-9_+=,.@/-]{1,32}",
            fullmatch=True,
        ))
        event_summary = _build_event_summary(identity_arn, "StopLogging")
        return event_summary, rule_choice

    elif rule_choice == "cross_account_role_assumption":
        identity_arn = draw(st.from_regex(
            r"arn:aws:iam::111111111111:(user|role)/[a-zA-Z0-9_+=,.@/-]{1,32}",
            fullmatch=True,
        ))
        event_summary = _build_event_summary(
            identity_arn, "AssumeRole",
            event_parameters={"roleArn": "arn:aws:iam::987654321098:role/CrossAccountRole"},
        )
        return event_summary, rule_choice

    else:  # root_user_activity
        event_summary = _build_event_summary("arn:aws:iam::111111111111:root", "CreateUser")
        return event_summary, rule_choice


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------

# Feature: phase-6-testing-and-documentation, Property 5: Detection finding validity
@given(scenario=triggering_event_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_detection_finding_validity(scenario, dynamodb_tables):
    """For any triggering event, findings have valid detection_type and confidence in [0, 100]."""
    event_summary, expected_rule = scenario
    put_item(dynamodb_tables["event_summary"], event_summary)
    findings = _run_detection(event_summary, dynamodb_tables)

    # At least one finding must be produced
    assert findings, f"Expected at least one finding for event_type={event_summary['event_type']}"

    # All findings must have valid structure
    for finding in findings:
        assert isinstance(finding.detection_type, str) and finding.detection_type, \
            "finding.detection_type must be a non-empty string"
        assert isinstance(finding.confidence, int), \
            f"finding.confidence must be int, got {type(finding.confidence)}"
        assert 0 <= finding.confidence <= 100, \
            f"finding.confidence={finding.confidence} out of range [0, 100]"

    # The expected rule must have fired
    matched = [f for f in findings if f.detection_type == expected_rule]
    assert matched, (
        f"Expected {expected_rule} finding, got: {[f.detection_type for f in findings]}"
    )
