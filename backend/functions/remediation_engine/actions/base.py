"""Base types for Remediation_Engine actions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionOutcome:
    """Result of a single remediation action execution or suppression."""

    action_name: str
    outcome: str          # executed | skipped | failed | suppressed
    reason: str | None    # populated for skipped / suppressed / failed
    details: dict[str, Any] = field(default_factory=dict)


class RemediationAction(ABC):
    """Abstract base class for all remediation actions."""

    action_name: str

    @abstractmethod
    def execute(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        config: dict[str, Any],
        dry_run: bool,
    ) -> ActionOutcome:
        """Execute the action against the identity.

        Must be idempotent — calling twice with the same arguments must
        produce the same AWS state and return an equivalent ActionOutcome.

        Args:
            identity_arn: ARN of the IAM identity to act on.
            incident: Full incident record from DynamoDB.
            config: Remediation config record (Risk_Mode, allowed_ip_ranges, etc.).
            dry_run: When True, behave as monitor mode — no AWS mutations.

        Returns:
            ActionOutcome describing what happened.
        """

    @abstractmethod
    def suppress(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        reason: str,
    ) -> ActionOutcome:
        """Return a suppressed ActionOutcome without performing any AWS calls.

        Args:
            identity_arn: ARN of the IAM identity.
            incident: Full incident record.
            reason: Human-readable suppression reason (e.g. "monitor_mode").

        Returns:
            ActionOutcome with outcome="suppressed".
        """
