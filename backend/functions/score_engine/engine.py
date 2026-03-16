"""RuleEngine: orchestrates all scoring rules and produces a ScoreResult."""
from __future__ import annotations

from datetime import datetime, timezone

from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.interfaces import ScoreResult, ScoringRule, classify_severity
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

try:
    from backend.functions.score_engine.rules import ALL_RULES
except ImportError:
    logger.warning("Rules package not found — RuleEngine will have no rules loaded")
    ALL_RULES = []


class RuleEngine:
    """Orchestrates evaluation of all scoring rules for a given ScoringContext."""

    def __init__(self) -> None:
        self.rules: list[ScoringRule] = [rule() for rule in ALL_RULES]

    def evaluate(self, context: ScoringContext) -> ScoreResult:
        """Evaluate all rules against the context and return a ScoreResult.

        Args:
            context: ScoringContext populated with identity data.

        Returns:
            ScoreResult with score, severity, contributing factors, and timestamp.
        """
        contributions: list[str] = []
        total = 0

        for rule in self.rules:
            try:
                points = rule.calculate(context.identity_arn, context)
            except Exception as exc:
                logger.warning(
                    "Rule evaluation failed — skipping",
                    extra={"rule_id": rule.rule_id, "error": str(exc)},
                )
                continue

            points = max(0, min(points, rule.max_contribution))
            if points > 0:
                contributions.append(f"{rule.rule_name}: +{points}")
                total += points

        total = min(total, 100)

        return ScoreResult(
            identity_arn=context.identity_arn,
            score_value=total,
            severity_level=classify_severity(total),
            calculation_timestamp=datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            contributing_factors=contributions,
        )
