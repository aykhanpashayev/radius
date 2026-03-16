"""PrivilegeEscalation detection rule."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.functions.detection_engine.interfaces import ContextAwareDetectionRule, Finding
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.detection_engine.context import DetectionContext

_DIRECT_ESCALATION_EVENTS = {"CreatePolicyVersion", "AddUserToGroup", "PassRole"}


class PrivilegeEscalationRule(ContextAwareDetectionRule):
    """Detects privilege escalation via direct IAM actions or combined patterns.

    Triggers on:
    - Direct single-event indicators: CreatePolicyVersion, AddUserToGroup, PassRole
    - Combined indicator: AttachUserPolicy following a recent CreateUser (within 60m)
    """

    rule_id = "privilege_escalation"
    rule_name = "PrivilegeEscalation"
    severity = "High"
    confidence = 80

    def evaluate_with_context(
        self,
        event_summary: dict[str, Any],
        context: "DetectionContext",
    ) -> Finding | None:
        identity_arn = event_summary.get("identity_arn", "")
        event_id = event_summary.get("event_id", "")
        event_name = extract_event_name(event_summary.get("event_type", ""))

        # Direct single-event indicators
        if event_name in _DIRECT_ESCALATION_EVENTS:
            return Finding(
                identity_arn=identity_arn,
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_id],
                description=f"Privilege escalation via {event_name}",
            )

        # Combined indicator: AttachUserPolicy following a recent CreateUser
        if event_name == "AttachUserPolicy":
            recent_names = {
                extract_event_name(e.get("event_type", ""))
                for e in context.recent_events_60m
            }
            if "CreateUser" in recent_names:
                return Finding(
                    identity_arn=identity_arn,
                    detection_type=self.rule_id,
                    severity=self.severity,
                    confidence=self.confidence,
                    related_event_ids=[event_id],
                    description="Privilege escalation: CreateUser followed by AttachUserPolicy",
                )

        return None
