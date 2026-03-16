"""UnusualServiceUsage detection rule."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.functions.detection_engine.interfaces import ContextAwareDetectionRule, Finding

if TYPE_CHECKING:
    from backend.functions.detection_engine.context import DetectionContext

_HIGH_RISK_SERVICES = {"sts", "iam", "organizations", "kms", "secretsmanager", "ssm"}


class UnusualServiceUsageRule(ContextAwareDetectionRule):
    """Detects first use of a high-risk service in the past 30 days.

    Triggers when the current event's service is in the high-risk set AND
    does not appear in prior_services_30d (events strictly before the current
    event timestamp — the current event is never pre-included).
    """

    rule_id = "unusual_service_usage"
    rule_name = "UnusualServiceUsage"
    severity = "Low"
    confidence = 60

    def evaluate_with_context(
        self,
        event_summary: dict[str, Any],
        context: "DetectionContext",
    ) -> Finding | None:
        event_type = event_summary.get("event_type", "")
        current_service = event_type.split(":")[0].lower() if ":" in event_type else ""

        if not current_service:
            return None

        if current_service in _HIGH_RISK_SERVICES and current_service not in context.prior_services_30d:
            return Finding(
                identity_arn=event_summary.get("identity_arn", ""),
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description=f"First use of high-risk service '{current_service}' in 30 days",
            )

        return None
