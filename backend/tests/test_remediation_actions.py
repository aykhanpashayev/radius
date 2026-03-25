"""Unit tests for remediation_engine actions with mocked boto3 IAM/SNS clients."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.functions.remediation_engine.actions.block_role_assumption import BlockRoleAssumptionAction
from backend.functions.remediation_engine.actions.disable_iam_user import DisableIAMUserAction
from backend.functions.remediation_engine.actions.notify_security_team import NotifySecurityTeamAction
from backend.functions.remediation_engine.actions.remove_risky_policies import RemoveRiskyPoliciesAction
from backend.functions.remediation_engine.actions.restrict_network_access import RestrictNetworkAccessAction

# ---------------------------------------------------------------------------
# Shared fixtures / helpers
# ---------------------------------------------------------------------------

_USER_ARN = "arn:aws:iam::123456789012:user/alice"
_ROLE_ARN = "arn:aws:iam::123456789012:role/my-role"
_ASSUMED_ROLE_ARN = "arn:aws:sts::123456789012:assumed-role/my-role/session"

_INCIDENT = {
    "incident_id": "inc-001",
    "identity_arn": _USER_ARN,
    "detection_type": "privilege_escalation",
    "severity": "High",
}

_CONFIG = {
    "risk_mode": "enforce",
    "allowed_ip_ranges": ["10.0.0.0/8"],
}


def _client_error(code: str, message: str = "error") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": message}}, "operation")


# ---------------------------------------------------------------------------
# DisableIAMUserAction
# ---------------------------------------------------------------------------

class TestDisableIAMUserAction:
    action = DisableIAMUserAction()

    def test_skips_non_user_arn(self):
        outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "skipped"
        assert outcome.reason == "identity_type_not_supported"

    def test_skips_assumed_role_arn(self):
        outcome = self.action.execute(_ASSUMED_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "skipped"

    def test_deactivates_active_keys(self):
        mock_iam = MagicMock()
        mock_iam.list_access_keys.return_value = {
            "AccessKeyMetadata": [
                {"AccessKeyId": "AKIA1", "Status": "Active"},
                {"AccessKeyId": "AKIA2", "Status": "Inactive"},
            ]
        }
        mock_iam.delete_login_profile.return_value = {}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        assert "AKIA1" in outcome.details["deactivated_key_ids"]
        assert "AKIA2" not in outcome.details["deactivated_key_ids"]
        mock_iam.update_access_key.assert_called_once_with(
            UserName="alice", AccessKeyId="AKIA1", Status="Inactive"
        )

    def test_handles_missing_login_profile(self):
        mock_iam = MagicMock()
        mock_iam.list_access_keys.return_value = {"AccessKeyMetadata": []}
        mock_iam.delete_login_profile.side_effect = _client_error("NoSuchEntityException")

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"

    def test_returns_failed_on_iam_error(self):
        mock_iam = MagicMock()
        mock_iam.list_access_keys.side_effect = _client_error("AccessDenied", "Access denied")

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "failed"
        assert "Access denied" in outcome.reason

    def test_suppress_returns_suppressed(self):
        outcome = self.action.suppress(_USER_ARN, _INCIDENT, "monitor_mode")
        assert outcome.outcome == "suppressed"
        assert outcome.reason == "monitor_mode"


# ---------------------------------------------------------------------------
# RemoveRiskyPoliciesAction
# ---------------------------------------------------------------------------

_RISKY_POLICY_DOC = {
    "Statement": [{"Effect": "Allow", "Action": ["iam:*"], "Resource": "*"}]
}
_SAFE_POLICY_DOC = {
    "Statement": [{"Effect": "Allow", "Action": ["cloudwatch:GetMetricData"], "Resource": "*"}]
}


class TestRemoveRiskyPoliciesAction:
    action = RemoveRiskyPoliciesAction()

    def _mock_iam_no_policies(self):
        mock = MagicMock()
        mock.list_attached_user_policies.return_value = {"AttachedPolicies": []}
        mock.list_user_policies.return_value = {"PolicyNames": []}
        return mock

    def test_skips_when_no_risky_policies_found(self):
        mock_iam = self._mock_iam_no_policies()
        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "skipped"
        assert outcome.reason == "no_risky_policies_found"

    def test_skips_non_user_non_role_arn(self):
        outcome = self.action.execute(_ASSUMED_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "skipped"
        assert outcome.reason == "identity_type_not_supported"

    def test_removes_risky_managed_policy(self):
        mock_iam = MagicMock()
        mock_iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [{"PolicyArn": "arn:aws:iam::123:policy/RiskyPolicy"}]
        }
        mock_iam.get_policy.return_value = {"Policy": {"DefaultVersionId": "v1"}}
        mock_iam.get_policy_version.return_value = {
            "PolicyVersion": {"Document": _RISKY_POLICY_DOC}
        }
        mock_iam.list_user_policies.return_value = {"PolicyNames": []}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        assert "arn:aws:iam::123:policy/RiskyPolicy" in outcome.details["removed"]
        mock_iam.detach_user_policy.assert_called_once()

    def test_skips_safe_managed_policy(self):
        mock_iam = MagicMock()
        mock_iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [{"PolicyArn": "arn:aws:iam::123:policy/SafePolicy"}]
        }
        mock_iam.get_policy.return_value = {"Policy": {"DefaultVersionId": "v1"}}
        mock_iam.get_policy_version.return_value = {
            "PolicyVersion": {"Document": _SAFE_POLICY_DOC}
        }
        mock_iam.list_user_policies.return_value = {"PolicyNames": []}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "skipped"
        assert outcome.reason == "no_risky_policies_found"

    def test_removes_risky_inline_policy(self):
        mock_iam = MagicMock()
        mock_iam.list_attached_user_policies.return_value = {"AttachedPolicies": []}
        mock_iam.list_user_policies.return_value = {"PolicyNames": ["InlineRisky"]}
        mock_iam.get_user_policy.return_value = {"PolicyDocument": _RISKY_POLICY_DOC}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        assert "InlineRisky" in outcome.details["removed"]
        mock_iam.delete_user_policy.assert_called_once_with(UserName="alice", PolicyName="InlineRisky")

    def test_tolerates_per_policy_failure(self):
        """A failure on one policy should not abort the whole action."""
        mock_iam = MagicMock()
        mock_iam.list_attached_user_policies.return_value = {
            "AttachedPolicies": [{"PolicyArn": "arn:aws:iam::123:policy/P1"}]
        }
        mock_iam.get_policy.side_effect = _client_error("AccessDenied")
        mock_iam.list_user_policies.return_value = {"PolicyNames": []}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        # failed list is populated but action still returns executed (not failed)
        assert outcome.outcome == "executed"
        assert "arn:aws:iam::123:policy/P1" in outcome.details["failed"]

    def test_works_for_role_identity(self):
        mock_iam = MagicMock()
        mock_iam.list_attached_role_policies.return_value = {"AttachedPolicies": []}
        mock_iam.list_role_policies.return_value = {"PolicyNames": []}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "skipped"
        assert outcome.reason == "no_risky_policies_found"


# ---------------------------------------------------------------------------
# BlockRoleAssumptionAction
# ---------------------------------------------------------------------------

_TRUST_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole",
        }
    ],
}


class TestBlockRoleAssumptionAction:
    action = BlockRoleAssumptionAction()

    def test_skips_non_role_arn(self):
        outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "skipped"
        assert outcome.reason == "identity_type_not_supported"

    def test_prepends_deny_statement(self):
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {
            "Role": {"AssumeRolePolicyDocument": _TRUST_POLICY}
        }

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        call_args = mock_iam.update_assume_role_policy.call_args
        updated_doc = json.loads(call_args.kwargs["PolicyDocument"])
        assert updated_doc["Statement"][0]["Sid"] == "RadiusBlockAssumption"
        assert updated_doc["Statement"][0]["Effect"] == "Deny"

    def test_stores_previous_trust_policy_in_details(self):
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {
            "Role": {"AssumeRolePolicyDocument": _TRUST_POLICY}
        }

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)

        previous = json.loads(outcome.details["previous_trust_policy"])
        assert previous == _TRUST_POLICY

    def test_idempotent_when_deny_already_present(self):
        policy_with_deny = {
            "Version": "2012-10-17",
            "Statement": [
                {"Sid": "RadiusBlockAssumption", "Effect": "Deny", "Principal": {"AWS": "*"}, "Action": "sts:AssumeRole"},
                _TRUST_POLICY["Statement"][0],
            ],
        }
        mock_iam = MagicMock()
        mock_iam.get_role.return_value = {"Role": {"AssumeRolePolicyDocument": policy_with_deny}}

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        mock_iam.update_assume_role_policy.assert_not_called()

    def test_returns_failed_on_iam_error(self):
        mock_iam = MagicMock()
        mock_iam.get_role.side_effect = _client_error("NoSuchEntityException", "Role not found")

        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "failed"


# ---------------------------------------------------------------------------
# RestrictNetworkAccessAction
# ---------------------------------------------------------------------------

class TestRestrictNetworkAccessAction:
    action = RestrictNetworkAccessAction()

    def test_attaches_inline_policy_to_user(self):
        mock_iam = MagicMock()
        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        mock_iam.put_user_policy.assert_called_once()
        call_kwargs = mock_iam.put_user_policy.call_args.kwargs
        assert call_kwargs["UserName"] == "alice"
        assert call_kwargs["PolicyName"] == "RadiusNetworkRestriction"

    def test_attaches_inline_policy_to_role(self):
        mock_iam = MagicMock()
        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)

        assert outcome.outcome == "executed"
        mock_iam.put_role_policy.assert_called_once()

    def test_policy_contains_allowed_ip_ranges(self):
        mock_iam = MagicMock()
        config = {**_CONFIG, "allowed_ip_ranges": ["192.168.1.0/24"]}
        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, config, dry_run=False)

        policy_doc = outcome.details["policy_document"]
        condition = policy_doc["Statement"][0]["Condition"]
        assert "192.168.1.0/24" in condition["NotIpAddress"]["aws:SourceIp"]

    def test_policy_denies_network_actions(self):
        mock_iam = MagicMock()
        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)

        policy_doc = outcome.details["policy_document"]
        stmt = policy_doc["Statement"][0]
        assert stmt["Effect"] == "Deny"
        assert "ec2:*" in stmt["Action"]
        assert "s3:*" in stmt["Action"]

    def test_skips_unsupported_identity_type(self):
        outcome = self.action.execute(_ASSUMED_ROLE_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "skipped"

    def test_returns_failed_on_iam_error(self):
        mock_iam = MagicMock()
        mock_iam.put_user_policy.side_effect = _client_error("AccessDenied", "Denied")
        with patch("boto3.client", return_value=mock_iam):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, _CONFIG, dry_run=False)
        assert outcome.outcome == "failed"


# ---------------------------------------------------------------------------
# NotifySecurityTeamAction
# ---------------------------------------------------------------------------

class TestNotifySecurityTeamAction:
    action = NotifySecurityTeamAction()

    def test_skips_publish_in_monitor_mode(self):
        config = {**_CONFIG, "risk_mode": "monitor"}
        outcome = self.action.execute(_USER_ARN, _INCIDENT, config, dry_run=False)
        assert outcome.outcome == "suppressed"
        assert outcome.reason == "monitor_mode"

    def test_publishes_in_alert_mode(self):
        config = {**_CONFIG, "risk_mode": "alert"}
        mock_sns = MagicMock()
        with patch("boto3.client", return_value=mock_sns), \
             patch.dict("os.environ", {"REMEDIATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123:topic"}):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, config, dry_run=False)

        assert outcome.outcome == "executed"
        mock_sns.publish.assert_called_once()

    def test_publishes_in_enforce_mode(self):
        config = {**_CONFIG, "risk_mode": "enforce"}
        mock_sns = MagicMock()
        with patch("boto3.client", return_value=mock_sns), \
             patch.dict("os.environ", {"REMEDIATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123:topic"}):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, config, dry_run=False)

        assert outcome.outcome == "executed"

    def test_fails_when_topic_arn_not_configured(self):
        config = {**_CONFIG, "risk_mode": "enforce"}
        with patch.dict("os.environ", {}, clear=True):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, config, dry_run=False)
        assert outcome.outcome == "failed"
        assert "REMEDIATION_TOPIC_ARN" in outcome.reason

    def test_returns_failed_on_sns_error(self):
        config = {**_CONFIG, "risk_mode": "enforce"}
        mock_sns = MagicMock()
        mock_sns.publish.side_effect = _client_error("AuthorizationError", "Not authorized")
        with patch("boto3.client", return_value=mock_sns), \
             patch.dict("os.environ", {"REMEDIATION_TOPIC_ARN": "arn:aws:sns:us-east-1:123:topic"}):
            outcome = self.action.execute(_USER_ARN, _INCIDENT, config, dry_run=False)
        assert outcome.outcome == "failed"

    def test_suppress_returns_suppressed(self):
        outcome = self.action.suppress(_USER_ARN, _INCIDENT, "monitor_mode")
        assert outcome.outcome == "suppressed"
        assert outcome.reason == "monitor_mode"
