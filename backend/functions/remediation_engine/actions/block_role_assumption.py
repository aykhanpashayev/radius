"""BlockRoleAssumptionAction — prepends a Deny statement to a role's trust policy."""

from __future__ import annotations

import json
from typing import Any

import boto3
from botocore.exceptions import ClientError

from backend.common.logging_utils import get_logger
from backend.functions.remediation_engine.actions.base import ActionOutcome, RemediationAction

logger = get_logger(__name__)

_DENY_SID = "RadiusBlockAssumption"


def _is_iam_role(identity_arn: str) -> bool:
    parts = identity_arn.split(":")
    return len(parts) >= 6 and parts[5].startswith("role/")


def _extract_role_name(identity_arn: str) -> str:
    return identity_arn.split("/")[-1]


class BlockRoleAssumptionAction(RemediationAction):
    """Prepend a Deny-all-assume-role statement to the role's trust policy."""

    action_name = "block_role_assumption"

    def execute(
        self,
        identity_arn: str,
        incident: dict[str, Any],
        config: dict[str, Any],
        dry_run: bool,
    ) -> ActionOutcome:
        if not _is_iam_role(identity_arn):
            return ActionOutcome(
                action_name=self.action_name,
                outcome="skipped",
                reason="identity_type_not_supported",
            )

        role_name = _extract_role_name(identity_arn)
        iam = boto3.client("iam")

        try:
            role = iam.get_role(RoleName=role_name)["Role"]
            trust_policy = role["AssumeRolePolicyDocument"]
            if isinstance(trust_policy, str):
                trust_policy = json.loads(trust_policy)

            previous_policy_json = json.dumps(trust_policy)

            # Skip if the deny statement is already present (idempotency)
            existing_sids = [s.get("Sid") for s in trust_policy.get("Statement", [])]
            if _DENY_SID not in existing_sids:
                deny_statement = {
                    "Sid": _DENY_SID,
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": "sts:AssumeRole",
                }
                updated_policy = dict(trust_policy)
                updated_policy["Statement"] = [deny_statement] + list(trust_policy.get("Statement", []))

                iam.update_assume_role_policy(
                    RoleName=role_name,
                    PolicyDocument=json.dumps(updated_policy),
                )

            logger.info("BlockRoleAssumptionAction executed", extra={"role_name": role_name})
            return ActionOutcome(
                action_name=self.action_name,
                outcome="executed",
                reason=None,
                details={"previous_trust_policy": previous_policy_json},
            )

        except ClientError as exc:
            error_msg = exc.response["Error"]["Message"]
            logger.error("BlockRoleAssumptionAction failed", extra={"role_name": role_name, "error": error_msg})
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
