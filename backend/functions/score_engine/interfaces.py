"""Scoring rule interfaces for Score_Engine.

These define the contracts that scoring rules must implement.
Phase 3: real scoring logic — ScoringRule extended with max_contribution.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def classify_severity(score: int | float) -> str:
    """Map a numeric score (0-100) to a severity level.

    Ranges:
        0-19:  Low
        20-39: Moderate
        40-59: High
        60-79: Very High
        80-100: Critical

    Args:
        score: Numeric blast radius score.

    Returns:
        Severity level string.
    """
    score = max(0, min(100, int(score)))
    if score < 20:
        return "Low"
    if score < 40:
        return "Moderate"
    if score < 60:
        return "High"
    if score < 80:
        return "Very High"
    return "Critical"


@dataclass
class ScoreResult:
    """Represents a calculated blast radius score."""

    identity_arn: str
    score_value: int
    severity_level: str
    calculation_timestamp: str
    contributing_factors: list[str] = field(default_factory=list)
    previous_score: int | None = None
    score_change: int | None = None


class ScoringRule(ABC):
    """Base interface for all scoring rules."""

    rule_id: str
    rule_name: str
    max_contribution: int

    @abstractmethod
    def calculate(self, identity_arn: str, context: "ScoringContext") -> int:
        """Calculate a score contribution for this rule.

        Args:
            identity_arn: Identity ARN being scored.
            context: ScoringContext with all data needed for scoring.

        Returns:
            Integer score contribution (0 to max_contribution).
        """
