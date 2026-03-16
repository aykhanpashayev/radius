"""APIBurstAnomaly detection rule."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.functions.detection_engine.interfaces import ContextAwareDetectionRule, Finding

if TYPE_CHECKING:
    from backend.functions.detection_engine.context import DetectionContext

_BURST_THRESHOLD = 20


class APIBurstAnomalyRule(ContextAwareDetectionRule):
    """Detects an abnormal burst of API calls within a 5-minute window.

    Triggers when 20 or more API calls are observed in recent_events_5m
    (derived in-memory from recent_events_60m — no extra DynamoDB query).
    """

    rule_id = "api_burst_anomaly"
    rule_name = "APIBurstAnomaly"
    severity = "Moderate"
    confidence = 65

    def evaluate_with_context(
        self,
        event_summary: dict[str, Any],
        context: "DetectionContext",
    ) -> Finding | None:
        call_count = len(context.recent_events_5m)

        if call_count >= _BURST_THRESHOLD:
            return Finding(
                identity_arn=event_summary.get("identity_arn", ""),
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description=f"{call_count} API calls in last 5 minutes",
            )

        return None
