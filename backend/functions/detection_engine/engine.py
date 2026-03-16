"""RuleEngine: orchestrates all detection rules and produces a list of Findings."""
from __future__ import annotations

from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.interfaces import (
    ContextAwareDetectionRule,
    DetectionRule,
    Finding,
)
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

try:
    from backend.functions.detection_engine.rules import ALL_RULES
except ImportError:
    logger.warning("Rules package not found — RuleEngine will have no rules loaded")
    ALL_RULES = []


class RuleEngine:
    """Orchestrates evaluation of all detection rules for a given event."""

    def __init__(self) -> None:
        self.rules: list[DetectionRule] = [rule() for rule in ALL_RULES]

    def evaluate(
        self,
        event_summary: dict,
        context: DetectionContext,
    ) -> list[Finding]:
        """Evaluate all rules against the event and context.

        Args:
            event_summary: Normalized Event_Summary dict.
            context: Pre-fetched DetectionContext for this identity.

        Returns:
            List of all triggered Findings (may be empty).
        """
        findings: list[Finding] = []

        for rule in self.rules:
            try:
                if isinstance(rule, ContextAwareDetectionRule):
                    finding = rule.evaluate_with_context(event_summary, context)
                else:
                    finding = rule.evaluate(event_summary)

                if finding is not None:
                    findings.append(finding)
            except Exception as exc:
                logger.warning(
                    "Rule evaluation failed — skipping",
                    extra={"rule_id": rule.rule_id, "error": str(exc)},
                )

        return findings
