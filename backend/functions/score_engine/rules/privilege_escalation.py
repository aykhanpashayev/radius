"""PrivilegeEscalation scoring rule.

Detects privilege escalation patterns by counting distinct escalation
indicators present in the identity's events within the scoring window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext


class PrivilegeEscalationRule(ScoringRule):
    """Scores based on the number of distinct privilege escalation indicators."""

    rule_id = "privilege_escalation"
    rule_name = "PrivilegeEscalation"
    max_contribution = 15

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        event_names = {extract_event_name(e.get("event_type", "")) for e in context.events}

        indicators = 0

        # Indicator 1: CreateUser AND AttachUserPolicy both present in same window
        if "CreateUser" in event_names and "AttachUserPolicy" in event_names:
            indicators += 1

        # Indicator 2: CreatePolicyVersion present
        if "CreatePolicyVersion" in event_names:
            indicators += 1

        # Indicator 3: AddUserToGroup present
        if "AddUserToGroup" in event_names:
            indicators += 1

        # Indicator 4: PassRole present
        if "PassRole" in event_names:
            indicators += 1

        if indicators == 0:
            return 0
        if indicators == 1:
            return 8
        return 15
