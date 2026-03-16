"""LoggingDisruption detection rule."""
from __future__ import annotations

from typing import Any

from backend.functions.detection_engine.interfaces import DetectionRule, Finding
from backend.common.aws_utils import extract_event_name

_DISRUPTION_EVENTS = {
    "StopLogging",
    "DeleteTrail",
    "UpdateTrail",
    "PutEventSelectors",
    "DeleteFlowLogs",
    "DeleteLogGroup",
    "DeleteLogStream",
}


class LoggingDisruptionRule(DetectionRule):
    """Detects attempts to disable or tamper with AWS logging infrastructure."""

    rule_id = "logging_disruption"
    rule_name = "LoggingDisruption"
    severity = "Critical"
    confidence = 95

    def evaluate(self, event_summary: dict[str, Any]) -> Finding | None:
        event_name = extract_event_name(event_summary.get("event_type", ""))

        if event_name in _DISRUPTION_EVENTS:
            return Finding(
                identity_arn=event_summary.get("identity_arn", ""),
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description=f"Logging disruption via {event_name}",
            )

        return None
