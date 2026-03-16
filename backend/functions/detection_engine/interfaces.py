"""Detection rule interfaces for Detection_Engine.

These define the contracts that future detection rules must implement.
Phase 2: interfaces only — no detection logic is implemented.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Finding:
    """Represents a detection finding produced by a rule."""

    identity_arn: str
    detection_type: str
    severity: str          # Low | Moderate | High | Very High | Critical
    confidence: int        # 0-100
    related_event_ids: list[str] = field(default_factory=list)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class DetectionRule(ABC):
    """Base interface for all detection rules.

    Future phases will implement concrete subclasses of this interface.
    """

    rule_id: str
    rule_name: str

    @abstractmethod
    def evaluate(self, event_summary: dict[str, Any]) -> Finding | None:
        """Evaluate an Event_Summary against this rule.

        Args:
            event_summary: Normalized Event_Summary dict from DynamoDB.

        Returns:
            A Finding if the rule triggered, or None if not.
        """
