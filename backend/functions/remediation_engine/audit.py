"""Remediation_Engine audit log helpers.

All writes go to the Remediation_Audit_Log DynamoDB table.

Public API:
  write_audit_entry()      — single action evaluation record
  write_audit_summary()    — summary record after all actions complete
  write_audit_suppressed() — safety-suppressed path convenience wrapper
  write_audit_no_match()   — no-rule-match path convenience wrapper
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import boto3

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions.base import ActionOutcome

logger = get_logger(__name__)

_TTL_DAYS = 365


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _ttl_timestamp() -> int:
    """Unix timestamp 365 days from now, used for DynamoDB TTL."""
    return int((datetime.now(tz=timezone.utc) + timedelta(days=_TTL_DAYS)).timestamp())


def _put_item(audit_table: str, item: dict[str, Any]) -> None:
    """Write a single item to the audit table, swallowing errors non-fatally."""
    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(audit_table)
        table.put_item(Item=item)
    except Exception as exc:
        logger.warning(
            "Failed to write audit entry (non-fatal)",
            extra={"audit_id": item.get("audit_id"), "error": str(exc)},
        )


def write_audit_entry(
    audit_table: str,
    incident: dict[str, Any],
    rule_id: str,
    action_name: str,
    outcome: ActionOutcome,
    risk_mode: str,
    dry_run: bool,
) -> None:
    """Write a single action evaluation record to the audit log.

    Args:
        audit_table: Name of the Remediation_Audit_Log DynamoDB table.
        incident: Incident dict (must contain incident_id, identity_arn).
        rule_id: ID of the rule that triggered this action.
        action_name: Name of the action evaluated.
        outcome: ActionOutcome returned by the action.
        risk_mode: Active risk mode (monitor | alert | enforce).
        dry_run: Whether the engine is running in dry-run mode.
    """
    item: dict[str, Any] = {
        "audit_id": str(uuid.uuid4()),
        "incident_id": incident.get("incident_id", "unknown"),
        "identity_arn": incident.get("identity_arn", "unknown"),
        "rule_id": rule_id,
        "action_name": action_name,
        "outcome": outcome.outcome,
        "risk_mode": risk_mode,
        "dry_run": dry_run,
        "timestamp": _now_iso(),
        "details": json.dumps(outcome.details or {}),
        "reason": outcome.reason or "",
        "ttl": _ttl_timestamp(),
    }
    _put_item(audit_table, item)


def write_audit_summary(
    audit_table: str,
    incident: dict[str, Any],
    outcomes: list[ActionOutcome],
    risk_mode: str,
    dry_run: bool,
) -> None:
    """Write a summary record after all actions have been evaluated.

    The summary uses action_name='remediation_complete' and includes
    counts of executed, skipped, failed, and suppressed outcomes.

    Args:
        audit_table: Name of the Remediation_Audit_Log DynamoDB table.
        incident: Incident dict.
        outcomes: All ActionOutcome objects from this evaluation run.
        risk_mode: Active risk mode.
        dry_run: Whether the engine is running in dry-run mode.
    """
    counts = {"executed": 0, "skipped": 0, "failed": 0, "suppressed": 0}
    for o in outcomes:
        if o.outcome in counts:
            counts[o.outcome] += 1

    item: dict[str, Any] = {
        "audit_id": str(uuid.uuid4()),
        "incident_id": incident.get("incident_id", "unknown"),
        "identity_arn": incident.get("identity_arn", "unknown"),
        "rule_id": "",
        "action_name": "remediation_complete",
        "outcome": "summary",
        "risk_mode": risk_mode,
        "dry_run": dry_run,
        "timestamp": _now_iso(),
        "details": json.dumps(counts),
        "reason": "",
        "ttl": _ttl_timestamp(),
    }
    _put_item(audit_table, item)


def write_audit_suppressed(
    audit_table: str,
    incident: dict[str, Any],
    suppression_reason: str,
    risk_mode: str,
    dry_run: bool,
) -> None:
    """Write an audit record for the safety-suppressed path.

    Convenience wrapper around write_audit_entry() for when safety controls
    block remediation before any rule matching occurs.

    Args:
        audit_table: Name of the Remediation_Audit_Log DynamoDB table.
        incident: Incident dict.
        suppression_reason: Reason string from check_safety_controls().
        risk_mode: Active risk mode.
        dry_run: Whether the engine is running in dry-run mode.
    """
    outcome = ActionOutcome(
        action_name="remediation_suppressed",
        outcome="suppressed",
        reason=suppression_reason,
    )
    write_audit_entry(
        audit_table,
        incident,
        rule_id="",
        action_name="remediation_suppressed",
        outcome=outcome,
        risk_mode=risk_mode,
        dry_run=dry_run,
    )


def write_audit_no_match(
    audit_table: str,
    incident: dict[str, Any],
    risk_mode: str,
    dry_run: bool,
) -> None:
    """Write an audit record for the no-rule-match path.

    Convenience wrapper for when no rules match the incident.

    Args:
        audit_table: Name of the Remediation_Audit_Log DynamoDB table.
        incident: Incident dict.
        risk_mode: Active risk mode.
        dry_run: Whether the engine is running in dry-run mode.
    """
    outcome = ActionOutcome(
        action_name="no_rules_matched",
        outcome="skipped",
        reason="no_rules_matched",
    )
    write_audit_entry(
        audit_table,
        incident,
        rule_id="",
        action_name="no_rules_matched",
        outcome=outcome,
        risk_mode=risk_mode,
        dry_run=dry_run,
    )
