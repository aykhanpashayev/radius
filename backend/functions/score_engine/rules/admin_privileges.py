"""AdminPrivileges scoring rule.

Awards points when an identity performs IAM write operations or accesses
a broad range of AWS services, indicating elevated privilege usage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext

IAM_WRITE_EVENTS = {
    "CreateUser",
    "CreateRole",
    "AttachUserPolicy",
    "AttachRolePolicy",
    "PutUserPolicy",
    "PutRolePolicy",
    "CreatePolicy",
    "CreatePolicyVersion",
}


class AdminPrivilegesRule(ScoringRule):
    """Detects IAM write activity and broad service usage."""

    rule_id = "admin_privileges"
    rule_name = "AdminPrivileges"
    max_contribution = 25

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        points = 0

        # Check for IAM write events
        event_names = {
            extract_event_name(e["event_type"])
            for e in context.events
            if "event_type" in e
        }
        if event_names & IAM_WRITE_EVENTS:
            points += 20

        # Check for broad service usage (5+ distinct services)
        services = {
            e["event_type"].split(":")[0]
            for e in context.events
            if ":" in e.get("event_type", "")
        }
        if len(services) >= 5:
            points += 5

        return min(points, 25)
