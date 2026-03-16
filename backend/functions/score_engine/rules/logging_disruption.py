"""LoggingDisruption scoring rule.

Awards maximum points when an identity performs any action that disrupts
logging or audit trail visibility (e.g. stopping CloudTrail, deleting log groups).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from backend.functions.score_engine.interfaces import ScoringRule
from backend.common.aws_utils import extract_event_name

if TYPE_CHECKING:
    from backend.functions.score_engine.context import ScoringContext

LOGGING_DISRUPTION_EVENTS = {
    "StopLogging",
    "DeleteTrail",
    "UpdateTrail",
    "PutEventSelectors",
    "DeleteFlowLogs",
    "DeleteLogGroup",
    "DeleteLogStream",
}


class LoggingDisruptionRule(ScoringRule):
    """Scores based on whether any logging/audit disruption events were observed."""

    rule_id = "logging_disruption"
    rule_name = "LoggingDisruption"
    max_contribution = 20

    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        if any(
            extract_event_name(e.get("event_type", "")) in LOGGING_DISRUPTION_EVENTS
            for e in context.events
        ):
            return 20
        return 0
