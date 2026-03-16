"""Property-based tests for detection rule correctness (Hypothesis)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.engine import RuleEngine
from backend.functions.detection_engine.interfaces import (
    ContextAwareDetectionRule,
    DetectionRule,
    Finding,
)
from backend.functions.detection_engine.rules import ALL_RULES

_VALID_SEVERITIES = {"Low", "Moderate", "High", "Very High", "Critical"}

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_arn_strategy = st.from_regex(
    r"arn:aws:iam::[0-9]{12}:(user|role)/[a-zA-Z0-9_+=,.@/-]{1,64}",
    fullmatch=True,
)

_event_type_strategy = st.one_of(
    st.just("iam:CreateUser"),
    st.just("iam:DeleteUser"),
    st.just("sts:AssumeRole"),
    st.just("iam:AttachUserPolicy"),
    st.just("iam:CreatePolicyVersion"),
    st.just("iam:AddUserToGroup"),
    st.just("iam:PassRole"),
    st.just("cloudtrail:StopLogging"),
    st.just("cloudtrail:DeleteTrail"),
    st.just("kms:Decrypt"),
    st.just("ec2:DescribeInstances"),
    st.text(min_size=1, max_size=50),
)

_event_summary_strategy = st.fixed_dictionaries({
    "event_id": st.uuids().map(str),
    "event_type": _event_type_strategy,
    "identity_arn": _arn_strategy,
    "identity_type": st.sampled_from(["IAMUser", "AssumedRole", "Root", "FederatedUser", ""]),
    "timestamp": st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 1, 1),
    ).map(lambda d: d.replace(tzinfo=timezone.utc).isoformat()),
    "event_parameters": st.fixed_dictionaries({
        "roleArn": st.one_of(
            st.just(""),
            st.from_regex(r"arn:aws:iam::[0-9]{12}:role/[a-zA-Z0-9_+=,.@/-]{1,64}", fullmatch=True),
        ),
    }),
})


def _recent_event_strategy(minutes_ago_max: int = 55):
    now = datetime.now(timezone.utc)
    return st.fixed_dictionaries({
        "event_id": st.uuids().map(str),
        "event_type": _event_type_strategy,
        "timestamp": st.integers(min_value=1, max_value=minutes_ago_max).map(
            lambda m: (now - timedelta(minutes=m)).isoformat()
        ),
    })


_detection_context_strategy = st.builds(
    DetectionContext,
    identity_arn=_arn_strategy,
    recent_events_60m=st.lists(_recent_event_strategy(), max_size=30),
    prior_services_30d=st.sets(
        st.sampled_from(["iam", "sts", "kms", "ec2", "s3", "organizations", "secretsmanager", "ssm"]),
        max_size=8,
    ),
)

# ---------------------------------------------------------------------------
# Property 1 — Finding validity
# ---------------------------------------------------------------------------

@given(event=_event_summary_strategy, ctx=_detection_context_strategy)
@settings(max_examples=100)
def test_property_finding_validity(event, ctx):
    """Every Finding produced has non-empty identity_arn, detection_type, and valid severity."""
    engine = RuleEngine()
    findings = engine.evaluate(event, ctx)
    for f in findings:
        assert f.identity_arn, "identity_arn must not be empty"
        assert f.detection_type, "detection_type must not be empty"
        assert f.severity in _VALID_SEVERITIES, f"Invalid severity: {f.severity}"


# ---------------------------------------------------------------------------
# Property 2 — Confidence bounds
# ---------------------------------------------------------------------------

@given(event=_event_summary_strategy, ctx=_detection_context_strategy)
@settings(max_examples=100)
def test_property_confidence_bounds(event, ctx):
    """confidence is always in [0, 100] for all findings."""
    engine = RuleEngine()
    findings = engine.evaluate(event, ctx)
    for f in findings:
        assert 0 <= f.confidence <= 100, f"confidence out of bounds: {f.confidence}"


# ---------------------------------------------------------------------------
# Property 3 — Rule identity (detection_type == rule_id)
# ---------------------------------------------------------------------------

@given(event=_event_summary_strategy, ctx=_detection_context_strategy)
@settings(max_examples=100)
def test_property_rule_identity(event, ctx):
    """finding.detection_type always equals the rule's rule_id."""
    for RuleCls in ALL_RULES:
        rule = RuleCls()
        try:
            if isinstance(rule, ContextAwareDetectionRule):
                finding = rule.evaluate_with_context(event, ctx)
            else:
                finding = rule.evaluate(event)
        except Exception:
            continue  # exceptions handled by engine; not a property violation here

        if finding is not None:
            assert finding.detection_type == rule.rule_id, (
                f"{rule.rule_name}: detection_type '{finding.detection_type}' != rule_id '{rule.rule_id}'"
            )


# ---------------------------------------------------------------------------
# Property 4 — No unhandled exceptions
# ---------------------------------------------------------------------------

@given(event=_event_summary_strategy, ctx=_detection_context_strategy)
@settings(max_examples=200)
def test_property_no_unhandled_exceptions(event, ctx):
    """Rules never propagate exceptions — engine always returns a list."""
    engine = RuleEngine()
    result = engine.evaluate(event, ctx)
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Property 5 — Determinism
# ---------------------------------------------------------------------------

@given(event=_event_summary_strategy, ctx=_detection_context_strategy)
@settings(max_examples=50)
def test_property_determinism(event, ctx):
    """Same event + context always produces the same findings."""
    engine = RuleEngine()
    findings_1 = engine.evaluate(event, ctx)
    findings_2 = engine.evaluate(event, ctx)

    assert len(findings_1) == len(findings_2)
    for f1, f2 in zip(findings_1, findings_2):
        assert f1.detection_type == f2.detection_type
        assert f1.severity == f2.severity
        assert f1.confidence == f2.confidence


# ---------------------------------------------------------------------------
# Property 6 — No false positives on empty input
# ---------------------------------------------------------------------------

def test_property_no_false_positives_on_empty_event():
    """Empty event dict never triggers any rule."""
    engine = RuleEngine()
    ctx = DetectionContext(identity_arn="")
    findings = engine.evaluate({}, ctx)
    assert findings == []


# ---------------------------------------------------------------------------
# Property 7 — Known triggers always fire
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("event_type,expected_rule_id", [
    ("cloudtrail:StopLogging", "logging_disruption"),
    ("cloudtrail:DeleteTrail", "logging_disruption"),
    ("iam:CreatePolicyVersion", "privilege_escalation"),
    ("iam:PassRole", "privilege_escalation"),
    ("iam:AddUserToGroup", "privilege_escalation"),
])
def test_property_known_triggers_always_fire(event_type, expected_rule_id):
    """Known trigger inputs always produce a Finding with the expected rule_id."""
    engine = RuleEngine()
    event = {
        "event_id": "known-trigger",
        "event_type": event_type,
        "identity_arn": "arn:aws:iam::111111111111:user/alice",
        "identity_type": "IAMUser",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_parameters": {},
    }
    ctx = DetectionContext(identity_arn="arn:aws:iam::111111111111:user/alice")
    findings = engine.evaluate(event, ctx)
    rule_ids = {f.detection_type for f in findings}
    assert expected_rule_id in rule_ids, (
        f"Expected rule '{expected_rule_id}' to fire for event_type '{event_type}', "
        f"but got: {rule_ids}"
    )
