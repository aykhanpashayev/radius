"""RoleChaining scoring rule.

Awards points based on the number of AssumeRole-type events observed,
indicating potential role chaining or privilege escalation via STS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext

ASSUME_ROLE_EVENTS = {"AssumeRole", "AssumeRoleWithSAML", "AssumeRoleWithWebIdentity"}


class RoleChainingRule(ScoringRule):
    """Scores based on the number of AssumeRole-type events observed."""

    rule_id = "role_chaining"
    rule_name = "RoleChaining"
    max_contribution = 10

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        count = sum(
            1 for e in context.events
            if extract_event_name(e.get("event_type", "")) in ASSUME_ROLE_EVENTS
        )

        if count == 0:
            return 0
        if count <= 2:
            return 5
        return 10
