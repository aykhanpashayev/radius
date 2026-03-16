"""Detection rule interfaces for Detection_Engine.

Phase 4: extended with ContextAwareDetectionRule and severity/rule_id class attributes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.functions.detection_engine.context import DetectionContext


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
    """Base interface for single-event detection rules.

    Single-event rules receive only the Event_Summary dict and must not
    perform any DynamoDB reads inside evaluate().
    """

    rule_id: str
    rule_name: str
    severity: str

    @abstractmethod
    def evaluate(self, event_summary: dict[str, Any]) -> Finding | None:
        """Evaluate an Event_Summary against this rule.

        Args:
            event_summary: Normalized Event_Summary dict from DynamoDB.

        Returns:
            A Finding if the rule triggered, or None if not.
        """


class ContextAwareDetectionRule(DetectionRule):
    """Interface for rules that require pre-fetched historical context.

    Context-aware rules receive a DetectionContext with pre-fetched
    DynamoDB data, keeping rules fully testable without mocking DynamoDB.
    """

    def evaluate(self, event_summary: dict[str, Any]) -> Finding | None:
        """Not used for context-aware rules — always returns None."""
        return None

    @abstractmethod
    def evaluate_with_context(
        self,
        event_summary: dict[str, Any],
        context: "DetectionContext",
    ) -> Finding | None:
        """Evaluate with pre-fetched historical context.

        Args:
            event_summary: Normalized Event_Summary dict.
            context: Pre-fetched DetectionContext for this identity.

        Returns:
            A Finding if the rule triggered, or None if not.
        """
