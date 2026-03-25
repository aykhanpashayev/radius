"""Remediation_Engine orchestrator.

RemediationRuleEngine.process() implements the full evaluation loop:
  load config → safety checks → match rules → collect actions →
  execute or suppress → notify → write summary audit record
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import boto3

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions import ALL_ACTIONS
from backend.functions.remediation_engine.actions.base import ActionOutcome
from backend.functions.remediation_engine.config import load_config

logger = get_logger(__name__)

# Severity rank used for min_severity comparisons (Requirement 2.4)
_SEVERITY_RANK: dict[str, int] = {
    "Low": 1,
    "Moderate": 2,
    "High": 3,
    "Very High": 4,
    "Critical": 5,
}


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class RemediationResult:
    incident_id: str
    identity_arn: str
    risk_mode: str
    dry_run: bool
    matched_rules: list[str] = field(default_factory=list)   # rule_ids
    action_outcomes: list[dict[str, Any]] = field(default_factory=list)
    executed: int = 0
    skipped: int = 0
    failed: int = 0
    suppressed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "identity_arn": self.identity_arn,
            "risk_mode": self.risk_mode,
            "dry_run": self.dry_run,
            "matched_rules": self.matched_rules,
            "action_outcomes": self.action_outcomes,
            "executed": self.executed,
            "skipped": self.skipped,
            "failed": self.failed,
            "suppressed": self.suppressed,
        }


# ---------------------------------------------------------------------------
# Rule matching helpers (tasks 4.3 and 4.4)
# ---------------------------------------------------------------------------

def match_rules(rules: list[dict[str, Any]], incident: dict[str, Any]) -> list[dict[str, Any]]:
    """Return active rules that match the given incident.

    Filters by:
    - rule["active"] must be True
    - severity_rank(incident.severity) >= severity_rank(rule.min_severity)
    - rule.detection_types: empty list matches all; otherwise incident.detection_type must be in the list
    - rule.identity_types: empty list matches all; otherwise incident.identity_type must be in the list

    Rules are returned in ascending priority order (lower int = higher priority).

    Args:
        rules: List of rule dicts from the config record.
        incident: Incident dict from Incident_Processor.

    Returns:
        Ordered list of matching rule dicts.
    """
    incident_severity = incident.get("severity", "")
    incident_detection_type = incident.get("detection_type", "")
    incident_identity_type = incident.get("identity_type", "")

    incident_rank = _SEVERITY_RANK.get(incident_severity, 0)

    matched: list[dict[str, Any]] = []
    for rule in rules:
        if not rule.get("active", False):
            continue

        # min_severity check
        rule_min_rank = _SEVERITY_RANK.get(rule.get("min_severity", "Low"), 1)
        if incident_rank < rule_min_rank:
            continue

        # detection_types check (empty = match all)
        detection_types = rule.get("detection_types") or []
        if detection_types and incident_detection_type not in detection_types:
            continue

        # identity_types check (empty = match all)
        identity_types = rule.get("identity_types") or []
        if identity_types and incident_identity_type not in identity_types:
            continue

        matched.append(rule)

    matched.sort(key=lambda r: r.get("priority", 999))
    return matched


def deduplicate_actions(action_names: list[str]) -> list[str]:
    """Return unique action names preserving first-occurrence order.

    Args:
        action_names: Flat list of action name strings (may contain duplicates).

    Returns:
        List with duplicates removed, original order preserved.
    """
    seen: set[str] = set()
    result: list[str] = []
    for name in action_names:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


# ---------------------------------------------------------------------------
# SNS notification helper
# ---------------------------------------------------------------------------

def _publish_notification(
    topic_arn: str,
    incident: dict[str, Any],
    risk_mode: str,
    outcomes: list[ActionOutcome],
) -> None:
    """Publish a remediation notification to the Remediation_Topic SNS topic."""
    actions_taken = [
        {"action": o.action_name, "outcome": o.outcome, "reason": o.reason}
        for o in outcomes
    ]
    message = {
        "incident_id": incident.get("incident_id"),
        "identity_arn": incident.get("identity_arn"),
        "detection_type": incident.get("detection_type"),
        "severity": incident.get("severity"),
        "risk_mode": risk_mode,
        "actions_taken": actions_taken,
        "timestamp": incident.get("creation_timestamp"),
        "dashboard_link": f"/incidents/{incident.get('incident_id')}",
    }
    try:
        sns = boto3.client("sns")
        sns.publish(
            TopicArn=topic_arn,
            Message=json.dumps(message),
            Subject="Radius Remediation Notification",
        )
    except Exception as exc:  # non-fatal
        logger.warning(
            "SNS publish failed (non-fatal)",
            extra={"topic_arn": topic_arn, "error": str(exc)},
        )


# ---------------------------------------------------------------------------
# RemediationRuleEngine
# ---------------------------------------------------------------------------

class RemediationRuleEngine:
    """Orchestrates the full remediation evaluation loop for a single incident."""

    def __init__(
        self,
        config_table: str,
        audit_table: str,
        topic_arn: str,
        dry_run: bool = False,
        correlation_id: str | None = None,
    ) -> None:
        self.config_table = config_table
        self.audit_table = audit_table
        self.topic_arn = topic_arn
        self.dry_run = dry_run
        self.correlation_id = correlation_id

    def process(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Run the full remediation evaluation loop.

        Steps:
          1. Load config (Risk_Mode + rules)
          2. Safety controls (exclusions, cooldown, rate limit)
          3. Match rules against the incident
          4. Collect deduplicated actions from matched rules
          5. Execute or suppress each action based on risk_mode / dry_run
          6. Publish SNS notification (alert + enforce modes only)
          7. Write summary audit record

        Args:
            incident: Incident dict with keys: incident_id, identity_arn,
                      detection_type, severity, identity_type, etc.

        Returns:
            RemediationResult.to_dict() describing what happened.
        """
        # Lazy imports to avoid circular dependencies at module load time
        from backend.functions.remediation_engine.audit import (
            write_audit_entry,
            write_audit_no_match,
            write_audit_suppressed,
            write_audit_summary,
        )
        from backend.functions.remediation_engine.safety import check_safety_controls

        incident_id = incident.get("incident_id", "unknown")
        identity_arn = incident.get("identity_arn", "unknown")

        logger.info(
            "Remediation_Engine processing incident",
            extra={"incident_id": incident_id, "identity_arn": identity_arn},
        )

        # 1. Load config
        config = load_config(self.config_table)
        # dry_run overrides risk_mode to monitor (Requirement 1.7)
        risk_mode = "monitor" if self.dry_run else config["risk_mode"]

        result = RemediationResult(
            incident_id=incident_id,
            identity_arn=identity_arn,
            risk_mode=risk_mode,
            dry_run=self.dry_run,
        )

        # 2. Safety controls
        suppression_reason = check_safety_controls(identity_arn, config, self.audit_table)
        if suppression_reason:
            logger.info(
                "Remediation suppressed by safety controls",
                extra={"incident_id": incident_id, "reason": suppression_reason},
            )
            write_audit_suppressed(
                self.audit_table, incident, suppression_reason, risk_mode, self.dry_run
            )
            result.suppressed = 1
            return result.to_dict()

        # 3. Match rules
        matched_rules = match_rules(config.get("rules", []), incident)
        if not matched_rules:
            logger.info(
                "No rules matched incident",
                extra={"incident_id": incident_id},
            )
            write_audit_no_match(self.audit_table, incident, risk_mode, self.dry_run)
            return result.to_dict()

        result.matched_rules = [r.get("rule_id", "") for r in matched_rules]

        # 4. Collect deduplicated actions across all matched rules
        all_action_names: list[str] = []
        action_to_rule: dict[str, str] = {}  # first rule that introduced each action
        for rule in matched_rules:
            for action_name in rule.get("actions", []):
                if action_name not in action_to_rule:
                    action_to_rule[action_name] = rule.get("rule_id", "")
                all_action_names.append(action_name)

        unique_actions = deduplicate_actions(all_action_names)

        # 5. Execute or suppress each action
        outcomes: list[ActionOutcome] = []
        for action_name in unique_actions:
            action = ALL_ACTIONS.get(action_name)
            if action is None:
                logger.warning(
                    "Unknown action name — skipping",
                    extra={"action_name": action_name, "incident_id": incident_id},
                )
                outcome = ActionOutcome(
                    action_name=action_name,
                    outcome="skipped",
                    reason="unknown_action",
                )
            elif risk_mode == "monitor":
                outcome = action.suppress(identity_arn, incident, "monitor_mode")
            else:
                outcome = action.execute(identity_arn, incident, config, self.dry_run)

            rule_id = action_to_rule.get(action_name, "")
            write_audit_entry(
                self.audit_table,
                incident,
                rule_id,
                action_name,
                outcome,
                risk_mode,
                self.dry_run,
            )
            outcomes.append(outcome)
            result.action_outcomes.append(
                {
                    "action": outcome.action_name,
                    "outcome": outcome.outcome,
                    "reason": outcome.reason,
                    "details": outcome.details,
                }
            )

        # Tally counts
        for o in outcomes:
            if o.outcome == "executed":
                result.executed += 1
            elif o.outcome == "skipped":
                result.skipped += 1
            elif o.outcome == "failed":
                result.failed += 1
            elif o.outcome == "suppressed":
                result.suppressed += 1

        # 6. Notify (alert + enforce modes only — Requirement 7.3)
        if risk_mode in ("alert", "enforce"):
            _publish_notification(self.topic_arn, incident, risk_mode, outcomes)

        # 7. Summary audit record
        write_audit_summary(self.audit_table, incident, outcomes, risk_mode, self.dry_run)

        logger.info(
            "Remediation_Engine completed",
            extra={
                "incident_id": incident_id,
                "executed": result.executed,
                "skipped": result.skipped,
                "failed": result.failed,
                "suppressed": result.suppressed,
            },
        )
        return result.to_dict()
