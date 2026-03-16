"""IAMPermissionsScope scoring rule.

Awards points based on the breadth of distinct IAM actions performed
by an identity, indicating how wide its IAM permission usage is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext


class IAMPermissionsScopeRule(ScoringRule):
    """Scores based on the number of distinct IAM event types observed."""

    rule_id = "iam_permissions_scope"
    rule_name = "IAMPermissionsScope"
    max_contribution = 20

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        iam_events = [
            e for e in context.events
            if e.get("event_type", "").startswith("iam:")
        ]

        distinct_actions = len({e["event_type"] for e in iam_events})

        if distinct_actions == 0:
            return 0
        if distinct_actions <= 4:
            return 5
        if distinct_actions <= 9:
            return 10
        return 20
