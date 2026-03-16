"""LateralMovement scoring rule.

Awards points based on indicators of lateral movement activity:
cross-account role assumption, EC2 instance profile usage, and federation events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_account_id, extract_event_name

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext


class LateralMovementRule(ScoringRule):
    """Scores based on indicators of lateral movement across accounts or services."""

    rule_id = "lateral_movement"
    rule_name = "LateralMovement"
    max_contribution = 10

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        points = 0

        identity_account = extract_account_id(identity_arn)

        # Indicator 1: Cross-account AssumeRole (+5)
        for e in context.events:
            if extract_event_name(e.get("event_type", "")) == "AssumeRole":
                role_arn = e.get("event_parameters", {}).get("roleArn", "")
                if role_arn:
                    target_account = extract_account_id(role_arn)
                    if target_account and target_account != identity_account:
                        points += 5
                        break  # only award once

        # Indicator 2: EC2 instance profile usage (+3)
        if any(extract_event_name(e.get("event_type", "")) == "RunInstances" for e in context.events):
            points += 3

        # Indicator 3: Federation events (+2)
        FEDERATION_EVENTS = {"GetFederationToken", "AssumeRoleWithWebIdentity"}
        if any(extract_event_name(e.get("event_type", "")) in FEDERATION_EVENTS for e in context.events):
            points += 2

        return min(points, 10)
