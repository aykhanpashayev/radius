"""Scoring correctness and DynamoDB write integration tests for Radius.

Tests that Score_Engine produces correct scores, severity levels, and
contributing factors, and that results are correctly written to DynamoDB.
Uses moto-mocked DynamoDB via conftest.py.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from backend.common.dynamodb_utils import get_item, put_item
from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.engine import RuleEngine
from backend.functions.score_engine.interfaces import ScoreResult, classify_severity

from backend.tests.integration.test_pipeline_e2e import _run_score_engine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ENGINE = RuleEngine()


def _make_event_summary(identity_arn: str, event_type: str) -> dict[str, Any]:
    """Build a minimal event_summary dict for seeding Event_Summary table."""
    return {
        "identity_arn": identity_arn,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": str(uuid.uuid4()),
        "event_type": event_type,
        "date_partition": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "account_id": identity_arn.split(":")[4] if len(identity_arn.split(":")) > 4 else "111111111111",
        "source_ip": "203.0.113.1",
        "user_agent": "aws-cli/2.15.0",
        "event_parameters": {},
        "region": "us-east-1",
    }


def _make_trust_relationship(source_arn: str, target_arn: str, relationship_type: str) -> dict[str, Any]:
    """Build a minimal trust_relationship dict."""
    return {
        "source_arn": source_arn,
        "target_arn": target_arn,
        "relationship_type": relationship_type,
        "source_account_id": source_arn.split(":")[4],
        "target_account_id": target_arn.split(":")[4],
        "discovery_timestamp": datetime.now(timezone.utc).isoformat(),
        "is_active": True,
        "last_used_timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# Example-based tests
# ---------------------------------------------------------------------------

def test_iam_write_events_produce_nonzero_score(dynamodb_tables):
    """AttachUserPolicy events produce a nonzero score above Low severity."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"

    # Seed 3 IAM mutation events to trigger IAMModificationRule at max contribution
    for _ in range(3):
        put_item(dynamodb_tables["event_summary"], _make_event_summary(identity_arn, "AttachUserPolicy"))

    result = _run_score_engine(identity_arn, dynamodb_tables)

    assert result.score_value > 0, "Expected nonzero score for IAM write events"
    assert result.severity_level != "Low", f"Expected severity above Low, got {result.severity_level}"


def test_empty_context_produces_zero_score(dynamodb_tables):
    """An identity with no events, trusts, or incidents scores zero."""
    identity_arn = "arn:aws:iam::111111111111:user/clean-user"

    # No data seeded — ScoringContext.build will return empty collections
    result = _run_score_engine(identity_arn, dynamodb_tables)

    assert result.score_value == 0, f"Expected score 0, got {result.score_value}"
    assert result.severity_level == "Low", f"Expected Low severity, got {result.severity_level}"


def test_logging_disruption_event_adds_contributing_factor(dynamodb_tables):
    """StopLogging event adds LoggingDisruption contributing factor."""
    identity_arn = "arn:aws:iam::111111111111:user/attacker"
    put_item(dynamodb_tables["event_summary"], _make_event_summary(identity_arn, "StopLogging"))

    result = _run_score_engine(identity_arn, dynamodb_tables)

    assert any("LoggingDisruption" in f for f in result.contributing_factors), (
        f"Expected LoggingDisruption factor, got: {result.contributing_factors}"
    )
    assert any("LoggingDisruption: +20" in f for f in result.contributing_factors), (
        f"Expected 'LoggingDisruption: +20', got: {result.contributing_factors}"
    )


def test_cross_account_trust_adds_contributing_factor(dynamodb_tables):
    """A CrossAccount trust relationship adds CrossAccountTrust contributing factor."""
    identity_arn = "arn:aws:iam::111111111111:user/dev-user"
    target_arn = "arn:aws:iam::987654321098:role/CrossAccountRole"

    put_item(
        dynamodb_tables["trust_relationship"],
        _make_trust_relationship(identity_arn, target_arn, "CrossAccount"),
    )

    result = _run_score_engine(identity_arn, dynamodb_tables)

    assert any("CrossAccountTrust" in f for f in result.contributing_factors), (
        f"Expected CrossAccountTrust factor, got: {result.contributing_factors}"
    )


def test_score_written_to_dynamodb(dynamodb_tables):
    """_run_score_engine writes a Blast_Radius_Score record to DynamoDB."""
    identity_arn = "arn:aws:iam::111111111111:user/test-user"
    put_item(dynamodb_tables["event_summary"], _make_event_summary(identity_arn, "StopLogging"))

    result = _run_score_engine(identity_arn, dynamodb_tables)

    record = get_item(
        dynamodb_tables["blast_radius_score"],
        {"identity_arn": identity_arn},
    )
    assert record is not None, "Expected Blast_Radius_Score record in DynamoDB"
    assert record["identity_arn"] == identity_arn
    assert record["score_value"] == result.score_value
    assert record["severity_level"] == result.severity_level


def test_blast_radius_score_record_fields(dynamodb_tables):
    """Written Blast_Radius_Score record contains all required fields."""
    identity_arn = "arn:aws:iam::111111111111:user/test-user"

    _run_score_engine(identity_arn, dynamodb_tables)

    record = get_item(
        dynamodb_tables["blast_radius_score"],
        {"identity_arn": identity_arn},
    )
    assert record is not None
    for field in ("identity_arn", "score_value", "severity_level", "calculation_timestamp", "contributing_factors"):
        assert field in record, f"Missing field: {field}"


def test_score_value_in_valid_range(dynamodb_tables):
    """Score value is always in [0, 100] for a variety of contexts."""
    identity_arn = "arn:aws:iam::111111111111:user/test-user"

    # Seed many events to push score high
    for event_type in ["StopLogging", "AttachUserPolicy", "AttachUserPolicy", "AttachUserPolicy"]:
        put_item(dynamodb_tables["event_summary"], _make_event_summary(identity_arn, event_type))
    put_item(
        dynamodb_tables["trust_relationship"],
        _make_trust_relationship(identity_arn, "arn:aws:iam::987654321098:role/R", "CrossAccount"),
    )

    result = _run_score_engine(identity_arn, dynamodb_tables)

    assert 0 <= result.score_value <= 100, f"score_value={result.score_value} out of range"


def test_severity_level_consistent_with_score(dynamodb_tables):
    """severity_level matches classify_severity(score_value) for written record."""
    identity_arn = "arn:aws:iam::111111111111:user/test-user"
    put_item(dynamodb_tables["event_summary"], _make_event_summary(identity_arn, "StopLogging"))

    result = _run_score_engine(identity_arn, dynamodb_tables)

    expected_severity = classify_severity(result.score_value)
    assert result.severity_level == expected_severity, (
        f"severity_level={result.severity_level!r} but classify_severity({result.score_value})={expected_severity!r}"
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

@st.composite
def scoring_context_strategy(draw):
    """Generate ScoringContext instances with varied events and trust relationships."""
    identity_arn = draw(st.from_regex(
        r"arn:aws:iam::[0-9]{12}:(user|role)/[a-zA-Z0-9_+=,.@/-]{1,32}",
        fullmatch=True,
    ))
    event_types = draw(st.lists(
        st.sampled_from([
            "AttachUserPolicy", "PutRolePolicy", "CreatePolicyVersion",
            "StopLogging", "DeleteTrail", "ListUsers", "CreateUser",
        ]),
        min_size=0,
        max_size=10,
    ))
    events = [
        {
            "identity_arn": identity_arn,
            "event_type": et,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": str(uuid.uuid4()),
            "event_parameters": {},
        }
        for et in event_types
    ]
    num_cross_account = draw(st.integers(min_value=0, max_value=5))
    trust_relationships = [
        {
            "source_arn": identity_arn,
            "target_arn": f"arn:aws:iam::987654321098:role/Role{i}",
            "relationship_type": "CrossAccount",
        }
        for i in range(num_cross_account)
    ]
    return ScoringContext(
        identity_arn=identity_arn,
        identity_profile={},
        events=events,
        trust_relationships=trust_relationships,
        open_incidents=[],
    )


# ---------------------------------------------------------------------------
# Property-based test P6
# ---------------------------------------------------------------------------

# **Validates: Requirements 1.2**
# Feature: phase-6-testing-and-documentation, Property 6: Score write round-trip
@given(ctx=scoring_context_strategy())
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_score_write_round_trip(ctx, dynamodb_tables):
    """For any ScoringContext, written Blast_Radius_Score has score in [0,100] and correct severity."""
    # Evaluate directly (no DynamoDB read needed — context is pre-built)
    result = _ENGINE.evaluate(ctx)

    # Write to DynamoDB (mirrors what _run_score_engine does)
    put_item(
        dynamodb_tables["blast_radius_score"],
        {
            "identity_arn": result.identity_arn,
            "score_value": result.score_value,
            "severity_level": result.severity_level,
            "calculation_timestamp": result.calculation_timestamp,
            "contributing_factors": result.contributing_factors,
        },
    )

    # Read back and verify
    record = get_item(
        dynamodb_tables["blast_radius_score"],
        {"identity_arn": result.identity_arn},
    )
    assert record is not None

    score = int(record["score_value"])
    assert 0 <= score <= 100, f"score_value={score} out of range [0, 100]"

    expected_severity = classify_severity(score)
    assert record["severity_level"] == expected_severity, (
        f"severity_level={record['severity_level']!r} != classify_severity({score})={expected_severity!r}"
    )
