"""CrossAccountTrust scoring rule.

Awards points based on the number of cross-account trust relationships
associated with an identity, indicating lateral movement risk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext


class CrossAccountTrustRule(ScoringRule):
    """Scores based on the number of cross-account trust relationships."""

    rule_id = "cross_account_trust"
    rule_name = "CrossAccountTrust"
    max_contribution = 15

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        cross_account = [
            t for t in context.trust_relationships
            if t.get("relationship_type") == "CrossAccount"
        ]
        count = len(cross_account)

        if count == 0:
            return 0
        if count == 1:
            return 5
        if count <= 3:
            return 10
        return 15
