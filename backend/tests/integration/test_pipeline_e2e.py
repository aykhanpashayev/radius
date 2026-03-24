"""End-to-end pipeline integration tests for Radius.

Tests the normalizer → collector → detection → scoring pipeline using
moto-mocked DynamoDB. All fixtures are provided by conftest.py.
"""

import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

import pytest

from backend.common.dynamodb_utils import get_item, put_item
from backend.common.errors import EventProcessingError, ValidationError
from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.engine import RuleEngine as DetectionRuleEngine
from backend.functions.event_normalizer.normalizer import parse_cloudtrail_event
from backend.functions.identity_collector.collector import (
    record_trust_relationship,
    upsert_identity_profile,
)
from backend.functions.incident_processor.processor import (
    append_event_to_incident,
    create_incident,
    find_duplicate,
    publish_alert,
    validate_finding,
)
from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.engine import RuleEngine as ScoreRuleEngine

# ---------------------------------------------------------------------------
# Pipeline helper functions
# ---------------------------------------------------------------------------

_ASSUME_ROLE_EVENTS = {"AssumeRole", "AssumeRoleWithSAML", "AssumeRoleWithWebIdentity"}


def _make_cloudtrail_event(
    event_name: str,
    identity_arn: str,
    account_id: str,
    event_time: str | None = None,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal valid CloudTrail event dict with EventBridge 'detail' wrapper."""
    return {
        "detail": {
            "eventVersion": "1.08",
            "userIdentity": {
                "type": "IAMUser",
                "arn": identity_arn,
                "accountId": account_id,
            },
            "eventTime": event_time or datetime.now(timezone.utc).isoformat(),
            "eventSource": f"{event_name.split(':')[0]}.amazonaws.com",
            "eventName": event_name.split(":")[-1],
            "awsRegion": "us-east-1",
            "sourceIPAddress": "203.0.113.1",
            "userAgent": "aws-cli/2.15.0",
            "requestParameters": extra_params or {},
            "responseElements": None,
            "eventID": str(uuid.uuid4()),
            "eventType": "AwsApiCall",
            "managementEvent": True,
            "recipientAccountId": account_id,
        }
    }


def _run_normalizer(raw_event: dict[str, Any]) -> dict[str, Any]:
    """Call parse_cloudtrail_event() and return event_summary dict."""
    return parse_cloudtrail_event(raw_event)


def _run_collector(
    event_summary: dict[str, Any],
    raw_event: dict[str, Any],
    tables: dict[str, str],
) -> None:
    """Call upsert_identity_profile() and conditionally record_trust_relationship()."""
    upsert_identity_profile(
        table_name=tables["identity_profile"],
        identity_arn=event_summary["identity_arn"],
        event_summary=event_summary,
    )
    if event_summary.get("event_type") in _ASSUME_ROLE_EVENTS:
        record_trust_relationship(
            table_name=tables["trust_relationship"],
            event_summary=event_summary,
            raw_event=raw_event.get("detail", raw_event),
        )


def _run_detection(
    event_summary: dict[str, Any],
    tables: dict[str, str],
) -> list:
    """Build DetectionContext and run detection RuleEngine.evaluate()."""
    ctx = DetectionContext.build(
        identity_arn=event_summary["identity_arn"],
        current_event_id=event_summary["event_id"],
        current_event_timestamp=event_summary["timestamp"],
        event_summary_table=tables["event_summary"],
    )
    engine = DetectionRuleEngine()
    return engine.evaluate(event_summary, ctx)


def _run_score_engine(
    identity_arn: str,
    tables: dict[str, str],
) -> Any:
    """Build ScoringContext, run score RuleEngine, write result to Blast_Radius_Score table."""
    ctx = ScoringContext.build(identity_arn, tables)
    engine = ScoreRuleEngine()
    result = engine.evaluate(ctx)
    put_item(
        tables["blast_radius_score"],
        {
            "identity_arn": result.identity_arn,
            "score_value": result.score_value,
            "severity_level": result.severity_level,
            "calculation_timestamp": result.calculation_timestamp,
            "contributing_factors": result.contributing_factors,
        },
    )
    return result


def _run_incident_processor(
    finding: Any,
    tables: dict[str, str],
    sns_topic_arn: str,
) -> tuple[dict[str, Any], bool]:
    """Run validate_finding, find_duplicate, create_incident or append_event_to_incident, publish_alert."""
    finding_dict = asdict(finding) if hasattr(finding, "__dataclass_fields__") else finding
    validate_finding(finding_dict)
    duplicate = find_duplicate(
        tables["incident"],
        finding_dict["identity_arn"],
        finding_dict["detection_type"],
    )
    if duplicate:
        append_event_to_incident(
            tables["incident"],
            duplicate["incident_id"],
            finding_dict.get("related_event_ids", []),
        )
        return duplicate, False
    incident = create_incident(tables["incident"], finding_dict)
    publish_alert(sns_topic_arn, incident)
    return incident, True


# ---------------------------------------------------------------------------
# Example-based tests
# ---------------------------------------------------------------------------

def test_event_summary_written_to_dynamodb(dynamodb_tables):
    """Normalizer output can be written to Event_Summary and retrieved by PK+SK."""
    identity_arn = "arn:aws:iam::111111111111:user/test-user"
    raw_event = _make_cloudtrail_event("CreateUser", identity_arn, "111111111111")

    event_summary = _run_normalizer(raw_event)
    put_item(dynamodb_tables["event_summary"], event_summary)

    record = get_item(
        dynamodb_tables["event_summary"],
        {"identity_arn": event_summary["identity_arn"], "timestamp": event_summary["timestamp"]},
    )

    assert record is not None
    assert record["identity_arn"] == identity_arn
    assert record["event_type"] == "CreateUser"
    assert "date_partition" in record


def test_identity_profile_created_on_first_event(dynamodb_tables):
    """Running a CreateUser event through the collector creates an Identity_Profile record."""
    identity_arn = "arn:aws:iam::111111111111:user/test-user"
    raw_event = _make_cloudtrail_event("CreateUser", identity_arn, "111111111111")

    event_summary = _run_normalizer(raw_event)
    _run_collector(event_summary, raw_event, dynamodb_tables)

    record = get_item(
        dynamodb_tables["identity_profile"],
        {"identity_arn": identity_arn},
    )

    assert record is not None
    assert record["identity_arn"] == identity_arn
    assert "identity_type" in record
    assert "account_id" in record
    assert "last_activity_timestamp" in record


def test_trust_relationship_written_on_assume_role(dynamodb_tables):
    """An AssumeRole event with a roleArn writes a Trust_Relationship record."""
    source_arn = "arn:aws:iam::111111111111:user/dev-user"
    target_role_arn = "arn:aws:iam::987654321098:role/CrossAccountRole"
    raw_event = _make_cloudtrail_event(
        "AssumeRole",
        source_arn,
        "111111111111",
        extra_params={"roleArn": target_role_arn},
    )

    event_summary = _run_normalizer(raw_event)
    _run_collector(event_summary, raw_event, dynamodb_tables)

    record = get_item(
        dynamodb_tables["trust_relationship"],
        {"source_arn": source_arn, "target_arn": target_role_arn},
    )

    assert record is not None
    assert record["source_arn"] == source_arn
    assert record["target_arn"] == target_role_arn
    assert record["relationship_type"] == "CrossAccount"
    assert "source_account_id" in record
    assert "target_account_id" in record


def test_invalid_event_raises_validation_error(dynamodb_tables):
    """An event missing eventName raises ValidationError during normalization."""
    raw_event = _make_cloudtrail_event("CreateUser", "arn:aws:iam::111111111111:user/u", "111111111111")
    # Remove eventName from detail
    raw_event["detail"]["eventName"] = ""
    # Blank eventName still passes field presence check; remove it entirely to trigger missing field
    del raw_event["detail"]["eventName"]

    with pytest.raises((ValidationError, EventProcessingError, KeyError)):
        _run_normalizer(raw_event)


def test_missing_user_identity_raises_error(dynamodb_tables):
    """An event missing userIdentity raises an error during normalization."""
    raw_event = _make_cloudtrail_event("CreateUser", "arn:aws:iam::111111111111:user/u", "111111111111")
    del raw_event["detail"]["userIdentity"]

    with pytest.raises((ValidationError, EventProcessingError, KeyError)):
        _run_normalizer(raw_event)


def test_missing_event_time_raises_error(dynamodb_tables):
    """An event missing eventTime raises ValidationError during normalization."""
    raw_event = _make_cloudtrail_event("CreateUser", "arn:aws:iam::111111111111:user/u", "111111111111")
    del raw_event["detail"]["eventTime"]

    with pytest.raises((ValidationError, EventProcessingError, KeyError)):
        _run_normalizer(raw_event)
