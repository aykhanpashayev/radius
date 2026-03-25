"""RemoveRiskyPoliciesAction — detaches/deletes policies with broad permissions."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions.base import ActionOutcome, RemediationAction

logger = get_logger(__name__)

# Actions that indicate a policy is "risky"
_RISKY_ACTIONS = {"iam:*", "sts:AssumeRole", "s3:*", "ec2:*", "lambda:*", "organizations:*"}


def _is_iam_user(identity_arn: str) -> bool:
    parts = identity_arn.split(":")
    return len(parts) >= 6 and parts[5].startswith("user/")


def _is_iam_role(identity_arn: str) -> bool:
    parts = identity_arn.split(":")
    return len(parts) >= 6 and parts[5].startswith("role/")


def _extract_name(identity_arn: str) -> str:
    return identity_arn.split("/")[-1]


def _policy_is_risky(policy_document: dict[str, Any]) -> bool:
    """Return True if any statement in the policy grants a risky action."""
    for statement in policy_document.get("Statement", []):
        if statement.get("Effect") != "Allow":
            continue
        actions = statement.get("Action", [])
        if isinstance(actions, str):
            actions = [actions]
        for action in actions:
            if action in _RISKY_ACTIONS:
                return True
    return False


class RemoveRiskyPoliciesAction(RemediationAction):
    """Remove managed and inline policies that grant broad/risky permissions."""

    action_name = "remove_risky_policies"

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
        iam = boto3.client("iam")
        removed: list[str] = []
        failed: list[str] = []

        try:
            # --- Managed (attached) policies ---
            if is_user:
                attached = iam.list_attached_user_policies(UserName=name).get("AttachedPolicies", [])
            else:
                attached = iam.list_attached_role_policies(RoleName=name).get("AttachedPolicies", [])

            for policy in attached:
                arn = policy["PolicyArn"]
                try:
                    # Fetch the default version to inspect the document
                    policy_meta = iam.get_policy(PolicyArn=arn)["Policy"]
                    version_id = policy_meta["DefaultVersionId"]
                    doc = iam.get_policy_version(PolicyArn=arn, VersionId=version_id)
                    document = doc["PolicyVersion"]["Document"]
                    if isinstance(document, str):
                        document = json.loads(document)

                    if _policy_is_risky(document):
                        if is_user:
                            iam.detach_user_policy(UserName=name, PolicyArn=arn)
                        else:
                            iam.detach_role_policy(RoleName=name, PolicyArn=arn)
                        removed.append(arn)
                except ClientError as exc:
                    logger.warning("Failed to process managed policy", extra={"arn": arn, "error": str(exc)})
                    failed.append(arn)

            # --- Inline policies ---
            if is_user:
                inline_names = iam.list_user_policies(UserName=name).get("PolicyNames", [])
            else:
                inline_names = iam.list_role_policies(RoleName=name).get("PolicyNames", [])

            for policy_name in inline_names:
                try:
                    if is_user:
                        doc = iam.get_user_policy(UserName=name, PolicyName=policy_name)
                        document = doc["PolicyDocument"]
                    else:
                        doc = iam.get_role_policy(RoleName=name, PolicyName=policy_name)
                        document = doc["PolicyDocument"]

                    if isinstance(document, str):
                        document = json.loads(document)

                    if _policy_is_risky(document):
                        if is_user:
                            iam.delete_user_policy(UserName=name, PolicyName=policy_name)
                        else:
                            iam.delete_role_policy(RoleName=name, PolicyName=policy_name)
                        removed.append(policy_name)
                except ClientError as exc:
                    logger.warning("Failed to process inline policy", extra={"policy_name": policy_name, "error": str(exc)})
                    failed.append(policy_name)

        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error("RemoveRiskyPoliciesAction failed", extra={"name": name, "error": error_msg})
            return ActionOutcome(
                action_name=self.action_name,
                outcome="failed",
                reason=error_msg,
            )

        if not removed and not failed:
            return ActionOutcome(
                action_name=self.action_name,
                outcome="skipped",
                reason="no_risky_policies_found",
            )

        logger.info(
            "RemoveRiskyPoliciesAction executed", extra={"identity_name": name, "removed": removed, "failed": failed}
        )
        return ActionOutcome(
            action_name=self.action_name,
            outcome="executed",
            reason=None,
            details={"removed": removed, "failed": failed},
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
