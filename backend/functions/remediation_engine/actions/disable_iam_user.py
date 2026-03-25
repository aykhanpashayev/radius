"""DisableIAMUserAction — deactivates access keys and deletes login profile."""

from __future__ import annotations

from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions.base import ActionOutcome, RemediationAction

logger = get_logger(__name__)


def _extract_username(identity_arn: str) -> str:
    """Extract the IAM username from an ARN like arn:aws:iam::123:user/alice."""
    return identity_arn.split("/")[-1]


def _is_iam_user(identity_arn: str) -> bool:
    """Return True when the ARN represents an IAM user."""
    parts = identity_arn.split(":")
    # arn:aws:iam::<account>:user/<name>
    return len(parts) >= 6 and parts[5].startswith("user/")


class DisableIAMUserAction(RemediationAction):
    """Deactivate all active access keys and delete the console login profile."""

    action_name = "disable_iam_user"

    def execute(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        config: dict[str, Any],
        dry_run: bool,
    ) -> ActionOutcome:
        if not _is_iam_user(identity_arn):
            return ActionOutcome(
                action_name=self.action_name,
                outcome="skipped",
                reason="identity_type_not_supported",
            )

        username = _extract_username(identity_arn)
        iam = boto3.client("iam")

        try:
            # Deactivate all active access keys
            keys_resp = iam.list_access_keys(UserName=username)
            deactivated: list[str] = []
            for key in keys_resp.get("AccessKeyMetadata", []):
                if key["Status"] == "Active":
                    iam.update_access_key(
                        UserName=username,
                        AccessKeyId=key["AccessKeyId"],
                        Status="Inactive",
                    )
                    deactivated.append(key["AccessKeyId"])

            # Delete login profile — ignore if it doesn't exist
            try:
                iam.delete_login_profile(UserName=username)
            except ClientError as exc:
                if exc.response["Error"]["Code"] != "NoSuchEntityException":
                    raise

            logger.info(
                "DisableIAMUserAction executed",
                extra={"username": username, "deactivated_keys": deactivated},
            )
            return ActionOutcome(
                action_name=self.action_name,
                outcome="executed",
                reason=None,
                details={"deactivated_key_ids": deactivated},
            )

        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error(
                "DisableIAMUserAction failed",
                extra={"username": username, "error": error_msg},
            )
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
