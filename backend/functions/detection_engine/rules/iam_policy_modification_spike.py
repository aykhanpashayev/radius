"""IAMPolicyModificationSpike detection rule."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from backend.functions.detection_engine.interfaces import ContextAwareDetectionRule, Finding
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.detection_engine.context import DetectionContext

_IAM_MUTATION_EVENTS = {
    "AttachUserPolicy",
    "AttachRolePolicy",
    "AttachGroupPolicy",
    "PutUserPolicy",
    "PutRolePolicy",
    "PutGroupPolicy",
    "CreatePolicyVersion",
    "SetDefaultPolicyVersion",
    "AddUserToGroup",
}

_SPIKE_THRESHOLD = 5


class IAMPolicyModificationSpikeRule(ContextAwareDetectionRule):
    """Detects a spike in IAM policy mutations within the last 60 minutes.

    Triggers when 5 or more IAM mutation events are observed in recent_events_60m.
    """

    rule_id = "iam_policy_modification_spike"
    rule_name = "IAMPolicyModificationSpike"
    severity = "High"
    confidence = 75

    def evaluate_with_context(
        self,
        event_summary: dict[str, Any],
        context: "DetectionContext",
    ) -> Finding | None:
        mutation_count = sum(
            1
            for e in context.recent_events_60m
            if extract_event_name(e.get("event_type", "")) in _IAM_MUTATION_EVENTS
        )

        if mutation_count >= _SPIKE_THRESHOLD:
            identity_arn = event_summary.get("identity_arn", "")
            event_id = event_summary.get("event_id", "")
            return Finding(
                identity_arn=identity_arn,
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_id],
                description=f"{mutation_count} IAM mutations in last 60 minutes",
            )

        return None
