"""Unit tests for RuleEngine and Detection_Engine lambda_handler."""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.engine import RuleEngine
from backend.functions.detection_engine.interfaces import (
    ContextAwareDetectionRule,
    DetectionRule,
    Finding,
)

_IDENTITY = "arn:aws:iam::111111111111:user/alice"


def _event(event_type: str = "iam:CreateUser") -> dict:
    return {
        "event_id": "evt-001",
        "event_type": event_type,
        "identity_arn": _IDENTITY,
        "identity_type": "IAMUser",
        "timestamp": "2026-03-16T12:00:00+00:00",
        "event_parameters": {},
    }


def _ctx() -> DetectionContext:
    return DetectionContext(identity_arn=_IDENTITY)


def _finding(rule_id: str = "test_rule") -> Finding:
    return Finding(
        identity_arn=_IDENTITY,
        detection_type=rule_id,
        severity="High",
        confidence=80,
        related_event_ids=["evt-001"],
        description="Test finding",
    )


# ---------------------------------------------------------------------------
# Stub rules for isolated RuleEngine tests
# ---------------------------------------------------------------------------

class _AlwaysFiringRule(DetectionRule):
    rule_id = "always_fires"
    rule_name = "AlwaysFires"
    severity = "High"

    def evaluate(self, event_summary):
        return _finding("always_fires")


class _NeverFiringRule(DetectionRule):
    rule_id = "never_fires"
    rule_name = "NeverFires"
    severity = "Low"

    def evaluate(self, event_summary):
        return None


class _ExplodingRule(DetectionRule):
    rule_id = "exploding"
    rule_name = "Exploding"
    severity = "Critical"

    def evaluate(self, event_summary):
        raise RuntimeError("boom")


class _AlwaysFiringContextRule(ContextAwareDetectionRule):
    rule_id = "always_fires_ctx"
    rule_name = "AlwaysFiresCtx"
    severity = "Moderate"

    def evaluate_with_context(self, event_summary, context):
        return _finding("always_fires_ctx")


# ---------------------------------------------------------------------------
# RuleEngine tests
# ---------------------------------------------------------------------------

class TestRuleEngine:
    def _engine_with(self, *rule_classes) -> RuleEngine:
        engine = RuleEngine.__new__(RuleEngine)
        engine.rules = [cls() for cls in rule_classes]
        return engine

    def test_returns_empty_list_when_no_rules_fire(self):
        engine = self._engine_with(_NeverFiringRule)
        findings = engine.evaluate(_event(), _ctx())
        assert findings == []

    def test_returns_finding_when_rule_fires(self):
        engine = self._engine_with(_AlwaysFiringRule)
        findings = engine.evaluate(_event(), _ctx())
        assert len(findings) == 1
        assert findings[0].detection_type == "always_fires"

    def test_returns_all_findings_when_multiple_rules_fire(self):
        engine = self._engine_with(_AlwaysFiringRule, _AlwaysFiringContextRule)
        findings = engine.evaluate(_event(), _ctx())
        assert len(findings) == 2
        types = {f.detection_type for f in findings}
        assert "always_fires" in types
        assert "always_fires_ctx" in types

    def test_exception_in_rule_is_caught_other_rules_still_run(self):
        engine = self._engine_with(_ExplodingRule, _AlwaysFiringRule)
        findings = engine.evaluate(_event(), _ctx())
        # Exploding rule skipped, AlwaysFiring still runs
        assert len(findings) == 1
        assert findings[0].detection_type == "always_fires"

    def test_context_aware_rule_receives_context(self):
        called_with = {}

        class _CapturingRule(ContextAwareDetectionRule):
            rule_id = "capturing"
            rule_name = "Capturing"
            severity = "Low"

            def evaluate_with_context(self, event_summary, context):
                called_with["context"] = context
                return None

        engine = self._engine_with(_CapturingRule)
        ctx = _ctx()
        engine.evaluate(_event(), ctx)
        assert called_with["context"] is ctx

    def test_no_rules_returns_empty_list(self):
        engine = self._engine_with()
        assert engine.evaluate(_event(), _ctx()) == []


# ---------------------------------------------------------------------------
# lambda_handler tests
# ---------------------------------------------------------------------------

class TestLambdaHandler:
    def _invoke_handler(self, event: dict, findings: list[Finding], invoke_side_effect=None):
        """Helper: patch env vars, engine, context, and lambda client, then call handler."""
        import os
        import importlib
        import sys

        env_vars = {
            "INCIDENT_PROCESSOR_ARN": "arn:aws:lambda:us-east-1:123456789012:function:Incident_Processor",
            "EVENT_SUMMARY_TABLE": "Event_Summary",
        }

        # Remove cached module so module-level code re-runs with patched env
        sys.modules.pop("backend.functions.detection_engine.handler", None)

        with patch.dict(os.environ, env_vars):
            import backend.functions.detection_engine.handler as handler_module

            mock_engine = MagicMock()
            mock_engine.evaluate.return_value = findings

            mock_lambda = MagicMock()
            if invoke_side_effect:
                mock_lambda.invoke.side_effect = invoke_side_effect

            mock_ctx = MagicMock(spec=DetectionContext)

            with patch.object(handler_module, "_engine", mock_engine), \
                 patch.object(handler_module, "_lambda_client", mock_lambda), \
                 patch("backend.functions.detection_engine.handler.DetectionContext") as mock_dc_cls:
                mock_dc_cls.build.return_value = mock_ctx
                result = handler_module.lambda_handler(event, None)

        return result, mock_lambda, mock_engine

    def test_zero_findings_returns_ok(self):
        result, _, _ = self._invoke_handler(_event(), [])
        assert result == {"status": "ok", "findings": 0, "failures": 0}

    def test_findings_forwarded_to_incident_processor(self):
        findings = [_finding("rule_a"), _finding("rule_b")]
        result, mock_lambda, _ = self._invoke_handler(_event(), findings)
        assert result["findings"] == 2
        assert result["failures"] == 0
        assert mock_lambda.invoke.call_count == 2

    def test_invoke_failure_counted_as_failure(self):
        findings = [_finding("rule_a"), _finding("rule_b")]
        result, mock_lambda, _ = self._invoke_handler(
            _event(), findings,
            invoke_side_effect=[None, Exception("invoke failed")]
        )
        assert result["findings"] == 1
        assert result["failures"] == 1

    def test_all_invoke_failures_still_returns_ok_status(self):
        findings = [_finding("rule_a")]
        result, _, _ = self._invoke_handler(
            _event(), findings,
            invoke_side_effect=Exception("network error")
        )
        assert result["status"] == "ok"
        assert result["failures"] == 1

    def test_no_placeholder_field_in_response(self):
        result, _, _ = self._invoke_handler(_event(), [])
        assert "placeholder" not in result

    def test_engine_receives_event_and_context(self):
        import os
        import sys

        sys.modules.pop("backend.functions.detection_engine.handler", None)

        env_vars = {
            "INCIDENT_PROCESSOR_ARN": "arn:aws:lambda:us-east-1:123456789012:function:Incident_Processor",
            "EVENT_SUMMARY_TABLE": "Event_Summary",
        }

        with patch.dict(os.environ, env_vars):
            import backend.functions.detection_engine.handler as handler_module

            mock_engine = MagicMock()
            mock_engine.evaluate.return_value = []
            mock_ctx = MagicMock(spec=DetectionContext)

            with patch.object(handler_module, "_engine", mock_engine), \
                 patch.object(handler_module, "_lambda_client", MagicMock()), \
                 patch("backend.functions.detection_engine.handler.DetectionContext") as mock_dc_cls:
                mock_dc_cls.build.return_value = mock_ctx
                ev = _event()
                handler_module.lambda_handler(ev, None)

        mock_engine.evaluate.assert_called_once_with(ev, mock_ctx)
