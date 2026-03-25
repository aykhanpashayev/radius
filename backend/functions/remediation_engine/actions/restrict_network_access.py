"""RestrictNetworkAccessAction — attaches an inline deny policy for network actions."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions.base import ActionOutcome, RemediationAction

logger = get_logger(__name__)

_POLICY_NAME = "RadiusNetworkRestriction"
_RESTRICTED_ACTIONS = ["ec2:*", "s3:*", "vpc:*"]


def _is_iam_user(identity_arn: str) -> bool:
    parts = identity_arn.split(":")
    return len(parts) >= 6 and parts[5].startswith("user/")


def _is_iam_role(identity_arn: str) -> bool:
    parts = identity_arn.split(":")
    return len(parts) >= 6 and parts[5].startswith("role/")


def _extract_name(identity_arn: str) -> str:
    return identity_arn.split("/")[-1]


def _build_deny_policy(allowed_ip_ranges: list[str]) -> dict[str, Any]:
    """Build a deny policy that blocks network actions from non-allowed IPs."""
    statement: dict[str, Any] = {
        "Sid": _POLICY_NAME,
        "Effect": "Deny",
        "Action": _RESTRICTED_ACTIONS,
        "Resource": "*",
    }
    if allowed_ip_ranges:
        statement["Condition"] = {
            "NotIpAddress": {"aws:SourceIp": allowed_ip_ranges}
        }
    return {
        "Version": "2012-10-17",
        "Statement": [statement],
    }


class RestrictNetworkAccessAction(RemediationAction):
    """Attach an inline deny policy restricting network-related actions."""

    action_name = "restrict_network_access"

    def execute(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        config: dict[str, Any],
        dry_run: bool,
    ) -> ActionOutcome:
        is_user = _is_iam_user(identity_arn)
        is_role = _is_iam_role(identity_arn)

        if not is_user and not is_role:
            return ActionOutcome(
                action_name=self.action_name,
                outcome="skipped",
                reason="identity_type_not_supported",
            )

        name = _extract_name(identity_arn)
        allowed_ip_ranges: list[str] = config.get("allowed_ip_ranges") or []
        policy_document = _build_deny_policy(allowed_ip_ranges)
        policy_json = json.dumps(policy_document)
        iam = boto3.client("iam")

        try:
            if is_user:
                iam.put_user_policy(
                    UserName=name,
                    PolicyName=_POLICY_NAME,
                    PolicyDocument=policy_json,
                )
            else:
                iam.put_role_policy(
                    RoleName=name,
                    PolicyName=_POLICY_NAME,
                    PolicyDocument=policy_json,
                )

            logger.info("RestrictNetworkAccessAction executed", extra={"identity_name": name})
            return ActionOutcome(
                action_name=self.action_name,
                outcome="executed",
                reason=None,
                details={"policy_document": policy_document},
            )

        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error("RestrictNetworkAccessAction failed", extra={"identity_name": name, "error": error_msg})
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
