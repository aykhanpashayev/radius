"""Unit tests for RuleEngine.evaluate()."""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.engine import RuleEngine
from backend.functions.score_engine.interfaces import ScoringRule, classify_severity

IDENTITY_ARN = "arn:aws:iam::123456789012:user/alice"


# ---------------------------------------------------------------------------
# Stub rules for controlled testing
# ---------------------------------------------------------------------------

class _FixedRule(ScoringRule):
    """A rule that always returns a fixed number of points."""

    def __init__(self, rule_id: str, rule_name: str, max_contribution: int, points: int):
        self.rule_id = rule_id
        self.rule_name = rule_name
        self.max_contribution = max_contribution
        self._points = points

    def calculate(self, identity_arn: str, context: ScoringContext) -> int:
        return self._points


class _ErrorRule(ScoringRule):
    """A rule that always raises an exception."""

    rule_id = "error_rule"
    rule_name = "ErrorRule"
    max_contribution = 10

    def calculate(self, identity_arn: str, context: ScoringContext) -> int:
        raise RuntimeError("Simulated rule failure")


def _engine_with_rules(rules: list[ScoringRule]) -> RuleEngine:
    engine = RuleEngine.__new__(RuleEngine)
    engine.rules = rules
    return engine


def _ctx(events=None, trust_relationships=None) -> ScoringContext:
    return ScoringContext(
        identity_arn=IDENTITY_ARN,
        identity_profile={},
        events=events or [],
        trust_relationships=trust_relationships or [],
        open_incidents=[],
    )


# ---------------------------------------------------------------------------
# Score capping
# ---------------------------------------------------------------------------

class TestScoreCapping:
    def test_total_capped_at_100(self):
        rules = [
            _FixedRule("r1", "Rule1", 60, 60),
            _FixedRule("r2", "Rule2", 60, 60),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.score_value == 100

    def test_total_not_capped_when_under_100(self):
        rules = [
            _FixedRule("r1", "Rule1", 30, 30),
            _FixedRule("r2", "Rule2", 40, 40),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.score_value == 70

    def test_total_exactly_100_not_modified(self):
        rules = [
            _FixedRule("r1", "Rule1", 50, 50),
            _FixedRule("r2", "Rule2", 50, 50),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.score_value == 100


# ---------------------------------------------------------------------------
# Contributing factors
# ---------------------------------------------------------------------------

class TestContributingFactors:
    def test_zero_contribution_rules_excluded(self):
        rules = [
            _FixedRule("r1", "Rule1", 20, 20),
            _FixedRule("r2", "Rule2", 20, 0),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert len(result.contributing_factors) == 1
        assert "Rule1" in result.contributing_factors[0]

    def test_all_zero_rules_produces_empty_factors(self):
        rules = [
            _FixedRule("r1", "Rule1", 20, 0),
            _FixedRule("r2", "Rule2", 20, 0),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.contributing_factors == []

    def test_contributing_factors_format(self):
        rules = [_FixedRule("r1", "MyRule", 25, 15)]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.contributing_factors == ["MyRule: +15"]

    def test_multiple_contributing_factors_all_present(self):
        rules = [
            _FixedRule("r1", "RuleA", 20, 10),
            _FixedRule("r2", "RuleB", 20, 5),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert "RuleA: +10" in result.contributing_factors
        assert "RuleB: +5" in result.contributing_factors

    def test_rule_contribution_clamped_to_max(self):
        """Rule returning more than max_contribution should be clamped."""
        rules = [_FixedRule("r1", "OverRule", 10, 999)]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.score_value == 10
        assert result.contributing_factors == ["OverRule: +10"]


# ---------------------------------------------------------------------------
# Severity consistency
# ---------------------------------------------------------------------------

class TestSeverityConsistency:
    @pytest.mark.parametrize("points,expected_severity", [
        (0,  "Low"),
        (10, "Low"),
        (19, "Low"),
        (20, "Moderate"),
        (39, "Moderate"),
        (40, "High"),
        (59, "High"),
        (60, "Very High"),
        (79, "Very High"),
        (80, "Critical"),
        (100, "Critical"),
    ])
    def test_severity_matches_classify_severity(self, points, expected_severity):
        rules = [_FixedRule("r1", "Rule1", 100, points)]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.severity_level == classify_severity(result.score_value)
        assert result.severity_level == expected_severity


# ---------------------------------------------------------------------------
# Empty context
# ---------------------------------------------------------------------------

class TestEmptyContext:
    def test_empty_context_score_is_0(self):
        engine = RuleEngine()  # real engine with all 8 rules
        result = engine.evaluate(_ctx())
        assert result.score_value == 0

    def test_empty_context_severity_is_low(self):
        engine = RuleEngine()
        result = engine.evaluate(_ctx())
        assert result.severity_level == "Low"

    def test_empty_context_no_contributing_factors(self):
        engine = RuleEngine()
        result = engine.evaluate(_ctx())
        assert result.contributing_factors == []

    def test_no_rules_engine_returns_zero(self):
        engine = _engine_with_rules([])
        result = engine.evaluate(_ctx())
        assert result.score_value == 0
        assert result.contributing_factors == []


# ---------------------------------------------------------------------------
# Error resilience
# ---------------------------------------------------------------------------

class TestErrorResilience:
    def test_failing_rule_skipped_others_still_evaluated(self):
        rules = [
            _ErrorRule(),
            _FixedRule("r2", "GoodRule", 20, 15),
        ]
        engine = _engine_with_rules(rules)
        result = engine.evaluate(_ctx())
        assert result.score_value == 15
        assert "GoodRule: +15" in result.contributing_factors

    def test_all_rules_fail_returns_zero(self):
        engine = _engine_with_rules([_ErrorRule(), _ErrorRule()])
        result = engine.evaluate(_ctx())
        assert result.score_value == 0


# ---------------------------------------------------------------------------
# Result fields
# ---------------------------------------------------------------------------

class TestResultFields:
    def test_identity_arn_set_correctly(self):
        engine = _engine_with_rules([])
        result = engine.evaluate(_ctx())
        assert result.identity_arn == IDENTITY_ARN

    def test_calculation_timestamp_is_iso8601(self):
        from datetime import datetime
        engine = _engine_with_rules([])
        result = engine.evaluate(_ctx())
        # Should parse without error
        dt = datetime.fromisoformat(result.calculation_timestamp)
        assert dt.tzinfo is not None  # must be timezone-aware
