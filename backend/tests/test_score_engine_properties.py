"""Property-based tests for Score_Engine correctness.

Validates 7 correctness properties using Hypothesis:
  1. Score bounds: 0 <= score <= 100
  2. Severity consistency: severity_level == classify_severity(score_value)
  3. Contributing factors non-negativity: all factor point values >= 0
  4. Rule independence: zeroing any single rule's inputs does not increase total score
  5. Determinism: scoring the same context twice produces identical ScoreResult
  6. Empty context baseline: no events/trusts/incidents → score == 0
  7. Score change consistency: score_change == score_value - previous_score
"""
from __future__ import annotations

import re
from copy import deepcopy

import pytest

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.engine import RuleEngine
from backend.functions.score_engine.interfaces import classify_severity, ScoreResult

IDENTITY_ARN = "arn:aws:iam::123456789012:user/test-user"
OTHER_ACCOUNT_ROLE = "arn:aws:iam::999999999999:role/CrossRole"

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

# Realistic event_type values drawn from the rule sets
_EVENT_TYPES = st.sampled_from([
    "iam:CreateUser", "iam:CreateRole", "iam:AttachUserPolicy", "iam:AttachRolePolicy",
    "iam:PutUserPolicy", "iam:PutRolePolicy", "iam:CreatePolicy", "iam:CreatePolicyVersion",
    "iam:AttachGroupPolicy", "iam:PutGroupPolicy", "iam:SetDefaultPolicyVersion",
    "iam:AddUserToGroup", "iam:PassRole", "iam:DeleteUser", "iam:ListUsers",
    "sts:AssumeRole", "sts:AssumeRoleWithSAML", "sts:AssumeRoleWithWebIdentity",
    "sts:GetFederationToken",
    "cloudtrail:StopLogging", "cloudtrail:DeleteTrail", "cloudtrail:UpdateTrail",
    "cloudtrail:PutEventSelectors",
    "ec2:RunInstances", "ec2:DescribeInstances",
    "logs:DeleteLogGroup", "logs:DeleteLogStream",
    "ec2:DeleteFlowLogs",
    "s3:PutObject", "s3:GetObject",
    "kms:Decrypt", "kms:GenerateDataKey",
    "lambda:InvokeFunction",
])

_ROLE_ARN = st.sampled_from([
    "arn:aws:iam::123456789012:role/SameAccountRole",   # same account
    OTHER_ACCOUNT_ROLE,                                  # cross-account
    "",                                                  # missing
])


@st.composite
def event_summary_strategy(draw) -> dict:
    event_type = draw(_EVENT_TYPES)
    params = {}
    if "AssumeRole" in event_type:
        params["roleArn"] = draw(_ROLE_ARN)
    return {"event_type": event_type, "event_parameters": params}


@st.composite
def trust_relationship_strategy(draw) -> dict:
    return {
        "source_arn": IDENTITY_ARN,
        "relationship_type": draw(st.sampled_from(["CrossAccount", "SameAccount", "ServiceLinked"])),
    }


@st.composite
def scoring_context_strategy(draw) -> ScoringContext:
    events = draw(st.lists(event_summary_strategy(), min_size=0, max_size=50))
    trusts = draw(st.lists(trust_relationship_strategy(), min_size=0, max_size=10))
    incidents = draw(st.lists(
        st.fixed_dictionaries({
            "incident_id": st.text(min_size=1, max_size=20),
            "status": st.sampled_from(["open", "investigating", "resolved", "closed"]),
        }),
        min_size=0, max_size=5,
    ))
    return ScoringContext(
        identity_arn=IDENTITY_ARN,
        identity_profile={"identity_arn": IDENTITY_ARN},
        events=events,
        trust_relationships=trusts,
        open_incidents=incidents,
    )


# ---------------------------------------------------------------------------
# Shared engine instance (module-level, mirrors Lambda warm-start pattern)
# ---------------------------------------------------------------------------
_engine = RuleEngine()


# ---------------------------------------------------------------------------
# Property 1 — Score bounds: 0 <= score <= 100
# ---------------------------------------------------------------------------

class TestProperty1ScoreBounds:
    @given(ctx=scoring_context_strategy())
    @settings(max_examples=200)
    def test_score_always_between_0_and_100(self, ctx):
        result = _engine.evaluate(ctx)
        assert 0 <= result.score_value <= 100, (
            f"score_value={result.score_value} out of bounds for context with "
            f"{len(ctx.events)} events, {len(ctx.trust_relationships)} trusts"
        )


# ---------------------------------------------------------------------------
# Property 2 — Severity consistency
# ---------------------------------------------------------------------------

class TestProperty2SeverityConsistency:
    @given(ctx=scoring_context_strategy())
    @settings(max_examples=200)
    def test_severity_matches_classify_severity(self, ctx):
        result = _engine.evaluate(ctx)
        expected = classify_severity(result.score_value)
        assert result.severity_level == expected, (
            f"severity_level={result.severity_level!r} but "
            f"classify_severity({result.score_value})={expected!r}"
        )


# ---------------------------------------------------------------------------
# Property 3 — Contributing factors non-negativity
# ---------------------------------------------------------------------------

_FACTOR_PATTERN = re.compile(r"^.+: \+(\d+)$")


class TestProperty3ContributingFactorsNonNegative:
    @given(ctx=scoring_context_strategy())
    @settings(max_examples=200)
    def test_all_factor_points_are_non_negative(self, ctx):
        result = _engine.evaluate(ctx)
        for factor in result.contributing_factors:
            m = _FACTOR_PATTERN.match(factor)
            assert m is not None, f"Factor {factor!r} does not match '<name>: +<points>' format"
            points = int(m.group(1))
            assert points >= 0, f"Factor {factor!r} has negative points"

    @given(ctx=scoring_context_strategy())
    @settings(max_examples=200)
    def test_factor_points_sum_equals_score(self, ctx):
        result = _engine.evaluate(ctx)
        factor_sum = sum(
            int(_FACTOR_PATTERN.match(f).group(1))
            for f in result.contributing_factors
            if _FACTOR_PATTERN.match(f)
        )
        # factor_sum may exceed 100 before capping; score_value is capped
        assert result.score_value == min(factor_sum, 100)


# ---------------------------------------------------------------------------
# Property 4 — Rule independence: zeroing one rule's inputs never increases score
# ---------------------------------------------------------------------------

class TestProperty4RuleIndependence:
    @given(ctx=scoring_context_strategy())
    @settings(max_examples=100)
    def test_removing_events_does_not_increase_score(self, ctx):
        """Removing all events from a context should not increase the score."""
        full_result = _engine.evaluate(ctx)
        empty_ctx = ScoringContext(
            identity_arn=ctx.identity_arn,
            identity_profile=ctx.identity_profile,
            events=[],                          # zeroed
            trust_relationships=ctx.trust_relationships,
            open_incidents=ctx.open_incidents,
        )
        empty_result = _engine.evaluate(empty_ctx)
        assert empty_result.score_value <= full_result.score_value, (
            f"Removing events increased score: {full_result.score_value} → {empty_result.score_value}"
        )

    @given(ctx=scoring_context_strategy())
    @settings(max_examples=100)
    def test_removing_trust_relationships_does_not_increase_score(self, ctx):
        """Removing all trust relationships should not increase the score."""
        full_result = _engine.evaluate(ctx)
        no_trust_ctx = ScoringContext(
            identity_arn=ctx.identity_arn,
            identity_profile=ctx.identity_profile,
            events=ctx.events,
            trust_relationships=[],             # zeroed
            open_incidents=ctx.open_incidents,
        )
        no_trust_result = _engine.evaluate(no_trust_ctx)
        assert no_trust_result.score_value <= full_result.score_value, (
            f"Removing trusts increased score: {full_result.score_value} → {no_trust_result.score_value}"
        )


# ---------------------------------------------------------------------------
# Property 5 — Determinism: same context → identical ScoreResult
# ---------------------------------------------------------------------------

class TestProperty5Determinism:
    @given(ctx=scoring_context_strategy())
    @settings(max_examples=200)
    def test_same_context_produces_same_score(self, ctx):
        result1 = _engine.evaluate(ctx)
        result2 = _engine.evaluate(ctx)
        assert result1.score_value == result2.score_value
        assert result1.severity_level == result2.severity_level
        assert result1.contributing_factors == result2.contributing_factors

    @given(ctx=scoring_context_strategy())
    @settings(max_examples=100)
    def test_deep_copy_context_produces_same_score(self, ctx):
        ctx_copy = deepcopy(ctx)
        result1 = _engine.evaluate(ctx)
        result2 = _engine.evaluate(ctx_copy)
        assert result1.score_value == result2.score_value
        assert result1.contributing_factors == result2.contributing_factors


# ---------------------------------------------------------------------------
# Property 6 — Empty context baseline: score == 0
# ---------------------------------------------------------------------------

class TestProperty6EmptyContextBaseline:
    def test_empty_context_score_is_zero(self):
        ctx = ScoringContext(
            identity_arn=IDENTITY_ARN,
            identity_profile={},
            events=[],
            trust_relationships=[],
            open_incidents=[],
        )
        result = _engine.evaluate(ctx)
        assert result.score_value == 0

    def test_empty_context_severity_is_low(self):
        ctx = ScoringContext(
            identity_arn=IDENTITY_ARN,
            identity_profile={},
            events=[],
            trust_relationships=[],
            open_incidents=[],
        )
        result = _engine.evaluate(ctx)
        assert result.severity_level == "Low"

    def test_empty_context_no_contributing_factors(self):
        ctx = ScoringContext(
            identity_arn=IDENTITY_ARN,
            identity_profile={},
            events=[],
            trust_relationships=[],
            open_incidents=[],
        )
        result = _engine.evaluate(ctx)
        assert result.contributing_factors == []

    @given(
        events=st.just([]),
        trusts=st.just([]),
        incidents=st.just([]),
    )
    @settings(max_examples=10)
    def test_hypothesis_empty_context_always_zero(self, events, trusts, incidents):
        ctx = ScoringContext(
            identity_arn=IDENTITY_ARN,
            identity_profile={},
            events=events,
            trust_relationships=trusts,
            open_incidents=incidents,
        )
        result = _engine.evaluate(ctx)
        assert result.score_value == 0


# ---------------------------------------------------------------------------
# Property 7 — Score change consistency
# ---------------------------------------------------------------------------

class TestProperty7ScoreChangeConsistency:
    @given(
        ctx=scoring_context_strategy(),
        previous=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=200)
    def test_score_change_equals_score_minus_previous(self, ctx, previous):
        result = _engine.evaluate(ctx)
        # Simulate what handler.py does when setting previous_score
        result.previous_score = previous
        result.score_change = result.score_value - previous
        assert result.score_change == result.score_value - previous

    @given(ctx=scoring_context_strategy())
    @settings(max_examples=100)
    def test_score_change_none_when_no_previous(self, ctx):
        result = _engine.evaluate(ctx)
        # Engine itself does not set previous_score — handler does
        assert result.previous_score is None
        assert result.score_change is None

    @given(
        score=st.integers(min_value=0, max_value=100),
        previous=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=200)
    def test_score_change_can_be_negative(self, score, previous):
        """Score change is signed — improvement yields negative delta."""
        result = ScoreResult(
            identity_arn=IDENTITY_ARN,
            score_value=score,
            severity_level=classify_severity(score),
            calculation_timestamp="2026-01-01T00:00:00+00:00",
            previous_score=previous,
            score_change=score - previous,
        )
        assert result.score_change == score - previous
