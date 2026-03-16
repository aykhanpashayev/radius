"""IAMModification scoring rule.

Awards points when an identity performs IAM mutation events,
indicating potential privilege escalation or policy tampering.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext

IAM_MUTATION_EVENTS = {
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


class IAMModificationRule(ScoringRule):
    """Scores based on the presence of IAM mutation events."""

    rule_id = "iam_modification"
    rule_name = "IAMModification"
    max_contribution = 20

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        count = sum(
            1 for e in context.events
            if extract_event_name(e.get("event_type", "")) in IAM_MUTATION_EVENTS
        )

        if count == 0:
            return 0
        if count <= 2:
            return 10
        return 20
