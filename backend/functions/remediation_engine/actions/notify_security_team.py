"""NotifySecurityTeamAction — publishes a structured alert to the Remediation SNS topic."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions.base import ActionOutcome, RemediationAction

logger = get_logger(__name__)


class NotifySecurityTeamAction(RemediationAction):
    """Publish a structured JSON notification to the Remediation_Topic SNS topic."""

    action_name = "notify_security_team"

    def execute(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        config: dict[str, Any],
        dry_run: bool,
    ) -> ActionOutcome:
        risk_mode = config.get("risk_mode", "monitor")

        # Skip publish in monitor mode — no side effects allowed
        if risk_mode == "monitor":
            return ActionOutcome(
                action_name=self.action_name,
                outcome="suppressed",
                reason="monitor_mode",
            )

        topic_arn = os.environ.get("REMEDIATION_TOPIC_ARN", "")
        if not topic_arn:
            return ActionOutcome(
                action_name=self.action_name,
                outcome="failed",
                reason="REMEDIATION_TOPIC_ARN not configured",
            )

        incident_id = incident.get("incident_id", "unknown")
        message = {
            "incident_id": incident_id,
            "identity_arn": identity_arn,
            "detection_type": incident.get("detection_type", ""),
            "severity": incident.get("severity", ""),
            "risk_mode": risk_mode,
            "actions_taken": incident.get("actions_taken", []),
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "dashboard_link": f"/incidents/{incident_id}",
        }

        try:
            sns = boto3.client("sns")
            sns.publish(
                TopicArn=topic_arn,
                Message=json.dumps(message),
                Subject="Radius Security Alert",
            )
            logger.info("NotifySecurityTeamAction executed", extra={"incident_id": incident_id})
            return ActionOutcome(
                action_name=self.action_name,
                outcome="executed",
                reason=None,
                details={"topic_arn": topic_arn},
            )

        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error("NotifySecurityTeamAction failed", extra={"incident_id": incident_id, "error": error_msg})
            return ActionOutcome(
                action_name=self.action_name,
                outcome="failed",
                reason=error_msg,
            )

    def suppress(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        reason: str,
    ) -> ActionOutcome:
        return ActionOutcome(
            action_name=self.action_name,
            outcome="suppressed",
            reason=reason,
        )
