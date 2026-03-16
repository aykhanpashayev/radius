"""CrossAccountRoleAssumption detection rule."""
from __future__ import annotations

from typing import Any

from backend.functions.detection_engine.interfaces import DetectionRule, Finding
from backend.common.aws_utils import extract_account_id, extract_event_name


class CrossAccountRoleAssumptionRule(DetectionRule):
    """Detects AssumeRole calls targeting a role in a different AWS account."""

    rule_id = "cross_account_role_assumption"
    rule_name = "CrossAccountRoleAssumption"
    severity = "Moderate"
    confidence = 70

    def evaluate(self, event_summary: dict[str, Any]) -> Finding | None:
        if extract_event_name(event_summary.get("event_type", "")) != "AssumeRole":
            return None

        role_arn = event_summary.get("event_parameters", {}).get("roleArn", "")
        identity_arn = event_summary.get("identity_arn", "")

        target_account = extract_account_id(role_arn)
        identity_account = extract_account_id(identity_arn)

        if not target_account or not identity_account:
            return None

        if target_account != identity_account:
            return Finding(
                identity_arn=identity_arn,
                detection_type=self.rule_id,
                severity=self.severity,
                confidence=self.confidence,
                related_event_ids=[event_summary.get("event_id", "")],
                description=(
                    f"Cross-account AssumeRole from account {identity_account} "
                    f"to account {target_account}"
                ),
            )

        return None
