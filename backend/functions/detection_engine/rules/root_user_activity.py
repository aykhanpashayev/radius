"""RootUserActivity detection rule."""
from __future__ import annotations

from typing import Any

from backend.functions.detection_engine.interfaces import DetectionRule, Finding


class RootUserActivityRule(DetectionRule):
    """Detects any API activity performed by the AWS root account.

    Primary check: identity_type == "Root"
    Fallback: ":root" substring in identity_arn (case-insensitive)
    """

    rule_id = "root_user_activity"
    rule_name = "RootUserActivity"
    severity = "Very High"
    confidence = 100

    def evaluate(self, event_summary: dict[str, Any]) -> Finding | None:
        identity_arn = event_summary.get("identity_arn", "")
        identity_type = event_summary.get("identity_type", "")

        # Primary check: explicit identity_type field
        if identity_type == "Root":
            return Finding(
                identity_arn=identity_arn,
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description="Root account activity detected",
            )

        # Fallback: ARN-based detection
        if ":root" in identity_arn.lower():
            return Finding(
                identity_arn=identity_arn,
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description="Root account activity detected (ARN-based)",
            )

        return None
