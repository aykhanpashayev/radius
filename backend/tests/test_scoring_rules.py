"""Unit tests for all 8 scoring rules.

Each rule is tested for:
- Zero input → 0 points
- Minimum threshold input → minimum non-zero points
- Maximum threshold input → max_contribution points
- Output never exceeds max_contribution
"""
from __future__ import annotations

import pytest

from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.rules.admin_privileges import AdminPrivilegesRule
from backend.functions.score_engine.rules.iam_permissions_scope import IAMPermissionsScopeRule
from backend.functions.score_engine.rules.iam_modification import IAMModificationRule
from backend.functions.score_engine.rules.logging_disruption import LoggingDisruptionRule
from backend.functions.score_engine.rules.cross_account_trust import CrossAccountTrustRule
from backend.functions.score_engine.rules.role_chaining import RoleChainingRule
from backend.functions.score_engine.rules.privilege_escalation import PrivilegeEscalationRule
from backend.functions.score_engine.rules.lateral_movement import LateralMovementRule

IDENTITY_ARN = "arn:aws:iam::123456789012:user/alice"
OTHER_ACCOUNT_ROLE = "arn:aws:iam::999999999999:role/CrossRole"


def _ctx(**kwargs) -> ScoringContext:
    """Build a minimal ScoringContext with overridable fields."""
    return ScoringContext(
        identity_arn=IDENTITY_ARN,
        identity_profile=kwargs.get("identity_profile", {}),
        events=kwargs.get("events", []),
        trust_relationships=kwargs.get("trust_relationships", []),
        open_incidents=kwargs.get("open_incidents", []),
    )


def _event(event_type: str, params: dict | None = None) -> dict:
    return {"event_type": event_type, "event_parameters": params or {}}


# ===========================================================================
# AdminPrivilegesRule  (max_contribution = 25)
# ===========================================================================

class TestAdminPrivilegesRule:
    rule = AdminPrivilegesRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_iam_write_event_awards_20(self):
        ctx = _ctx(events=[_event("iam:CreateUser")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 20

    def test_iam_write_plus_5_services_awards_25(self):
        events = [
            _event("iam:CreateUser"),
            _event("s3:PutObject"),
            _event("ec2:RunInstances"),
            _event("sts:AssumeRole"),
            _event("lambda:InvokeFunction"),
            _event("kms:Decrypt"),
        ]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 25

    def test_5_services_without_iam_write_awards_5(self):
        events = [
            _event("s3:PutObject"),
            _event("ec2:RunInstances"),
            _event("sts:AssumeRole"),
            _event("lambda:InvokeFunction"),
            _event("kms:Decrypt"),
        ]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_output_never_exceeds_max_contribution(self):
        events = [_event("iam:CreateUser")] + [_event(f"svc{i}:Action") for i in range(10)]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution

    def test_all_iam_write_events_detected(self):
        for action in ["CreateUser", "CreateRole", "AttachUserPolicy", "AttachRolePolicy",
                       "PutUserPolicy", "PutRolePolicy", "CreatePolicy", "CreatePolicyVersion"]:
            ctx = _ctx(events=[_event(f"iam:{action}")])
            assert self.rule.calculate(IDENTITY_ARN, ctx) >= 20


# ===========================================================================
# IAMPermissionsScopeRule  (max_contribution = 20)
# ===========================================================================

class TestIAMPermissionsScopeRule:
    rule = IAMPermissionsScopeRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_iam_events_returns_0(self):
        ctx = _ctx(events=[_event("s3:PutObject"), _event("ec2:RunInstances")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_1_distinct_iam_action_returns_5(self):
        ctx = _ctx(events=[_event("iam:CreateUser"), _event("iam:CreateUser")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_4_distinct_iam_actions_returns_5(self):
        events = [_event(f"iam:Action{i}") for i in range(4)]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_5_distinct_iam_actions_returns_10(self):
        events = [_event(f"iam:Action{i}") for i in range(5)]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_9_distinct_iam_actions_returns_10(self):
        events = [_event(f"iam:Action{i}") for i in range(9)]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_10_distinct_iam_actions_returns_20(self):
        events = [_event(f"iam:Action{i}") for i in range(10)]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 20

    def test_output_never_exceeds_max_contribution(self):
        events = [_event(f"iam:Action{i}") for i in range(50)]
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution


# ===========================================================================
# IAMModificationRule  (max_contribution = 20)
# ===========================================================================

class TestIAMModificationRule:
    rule = IAMModificationRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_mutation_events_returns_0(self):
        ctx = _ctx(events=[_event("iam:CreateUser"), _event("s3:PutObject")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_1_mutation_event_returns_10(self):
        ctx = _ctx(events=[_event("iam:AttachUserPolicy")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_2_mutation_events_returns_10(self):
        ctx = _ctx(events=[_event("iam:AttachUserPolicy"), _event("iam:PutRolePolicy")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_3_mutation_events_returns_20(self):
        ctx = _ctx(events=[
            _event("iam:AttachUserPolicy"),
            _event("iam:PutRolePolicy"),
            _event("iam:AddUserToGroup"),
        ])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 20

    def test_output_never_exceeds_max_contribution(self):
        events = [_event("iam:AttachUserPolicy")] * 100
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution

    def test_all_mutation_events_counted(self):
        mutation_events = [
            "AttachUserPolicy", "AttachRolePolicy", "AttachGroupPolicy",
            "PutUserPolicy", "PutRolePolicy", "PutGroupPolicy",
            "CreatePolicyVersion", "SetDefaultPolicyVersion", "AddUserToGroup",
        ]
        ctx = _ctx(events=[_event(f"iam:{e}") for e in mutation_events])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 20


# ===========================================================================
# LoggingDisruptionRule  (max_contribution = 20)
# ===========================================================================

class TestLoggingDisruptionRule:
    rule = LoggingDisruptionRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_disruption_events_returns_0(self):
        ctx = _ctx(events=[_event("iam:CreateUser"), _event("s3:PutObject")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_any_disruption_event_returns_20(self):
        for action in ["StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors",
                       "DeleteFlowLogs", "DeleteLogGroup", "DeleteLogStream"]:
            ctx = _ctx(events=[_event(f"cloudtrail:{action}")])
            assert self.rule.calculate(IDENTITY_ARN, ctx) == 20, f"Failed for {action}"

    def test_output_never_exceeds_max_contribution(self):
        events = [_event("cloudtrail:StopLogging")] * 5
        ctx = _ctx(events=events)
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution

    def test_disruption_mixed_with_other_events_still_returns_20(self):
        ctx = _ctx(events=[_event("iam:CreateUser"), _event("cloudtrail:DeleteTrail")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 20


# ===========================================================================
# CrossAccountTrustRule  (max_contribution = 15)
# ===========================================================================

class TestCrossAccountTrustRule:
    rule = CrossAccountTrustRule()

    def _trust(self, relationship_type: str = "CrossAccount") -> dict:
        return {"source_arn": IDENTITY_ARN, "relationship_type": relationship_type}

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_cross_account_trusts_returns_0(self):
        ctx = _ctx(trust_relationships=[self._trust("SameAccount")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_1_cross_account_trust_returns_5(self):
        ctx = _ctx(trust_relationships=[self._trust()])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_2_cross_account_trusts_returns_10(self):
        ctx = _ctx(trust_relationships=[self._trust(), self._trust()])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_3_cross_account_trusts_returns_10(self):
        ctx = _ctx(trust_relationships=[self._trust()] * 3)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_4_cross_account_trusts_returns_15(self):
        ctx = _ctx(trust_relationships=[self._trust()] * 4)
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 15

    def test_output_never_exceeds_max_contribution(self):
        ctx = _ctx(trust_relationships=[self._trust()] * 20)
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution


# ===========================================================================
# RoleChainingRule  (max_contribution = 10)
# ===========================================================================

class TestRoleChainingRule:
    rule = RoleChainingRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_assume_role_events_returns_0(self):
        ctx = _ctx(events=[_event("iam:CreateUser")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_1_assume_role_returns_5(self):
        ctx = _ctx(events=[_event("sts:AssumeRole")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_2_assume_role_events_returns_5(self):
        ctx = _ctx(events=[_event("sts:AssumeRole"), _event("sts:AssumeRoleWithSAML")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_3_assume_role_events_returns_10(self):
        ctx = _ctx(events=[
            _event("sts:AssumeRole"),
            _event("sts:AssumeRoleWithSAML"),
            _event("sts:AssumeRoleWithWebIdentity"),
        ])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 10

    def test_output_never_exceeds_max_contribution(self):
        ctx = _ctx(events=[_event("sts:AssumeRole")] * 50)
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution

    def test_all_assume_role_variants_counted(self):
        for action in ["AssumeRole", "AssumeRoleWithSAML", "AssumeRoleWithWebIdentity"]:
            ctx = _ctx(events=[_event(f"sts:{action}")])
            assert self.rule.calculate(IDENTITY_ARN, ctx) == 5


# ===========================================================================
# PrivilegeEscalationRule  (max_contribution = 15)
# ===========================================================================

class TestPrivilegeEscalationRule:
    rule = PrivilegeEscalationRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_indicators_returns_0(self):
        ctx = _ctx(events=[_event("s3:PutObject")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_1_indicator_create_user_and_attach_policy_returns_8(self):
        ctx = _ctx(events=[_event("iam:CreateUser"), _event("iam:AttachUserPolicy")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 8

    def test_1_indicator_create_policy_version_returns_8(self):
        ctx = _ctx(events=[_event("iam:CreatePolicyVersion")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 8

    def test_1_indicator_add_user_to_group_returns_8(self):
        ctx = _ctx(events=[_event("iam:AddUserToGroup")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 8

    def test_1_indicator_pass_role_returns_8(self):
        ctx = _ctx(events=[_event("iam:PassRole")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 8

    def test_2_indicators_returns_15(self):
        ctx = _ctx(events=[_event("iam:CreatePolicyVersion"), _event("iam:PassRole")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 15

    def test_all_4_indicators_returns_15(self):
        ctx = _ctx(events=[
            _event("iam:CreateUser"),
            _event("iam:AttachUserPolicy"),
            _event("iam:CreatePolicyVersion"),
            _event("iam:AddUserToGroup"),
            _event("iam:PassRole"),
        ])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 15

    def test_create_user_without_attach_policy_not_indicator(self):
        ctx = _ctx(events=[_event("iam:CreateUser")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_output_never_exceeds_max_contribution(self):
        ctx = _ctx(events=[
            _event("iam:CreateUser"), _event("iam:AttachUserPolicy"),
            _event("iam:CreatePolicyVersion"), _event("iam:AddUserToGroup"),
            _event("iam:PassRole"),
        ])
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution


# ===========================================================================
# LateralMovementRule  (max_contribution = 10)
# ===========================================================================

class TestLateralMovementRule:
    rule = LateralMovementRule()

    def test_zero_input(self):
        assert self.rule.calculate(IDENTITY_ARN, _ctx()) == 0

    def test_no_lateral_events_returns_0(self):
        ctx = _ctx(events=[_event("iam:CreateUser")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_cross_account_assume_role_awards_5(self):
        ctx = _ctx(events=[_event("sts:AssumeRole", {"roleArn": OTHER_ACCOUNT_ROLE})])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5

    def test_same_account_assume_role_awards_0(self):
        same_account_role = "arn:aws:iam::123456789012:role/SameRole"
        ctx = _ctx(events=[_event("sts:AssumeRole", {"roleArn": same_account_role})])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 0

    def test_run_instances_awards_3(self):
        ctx = _ctx(events=[_event("ec2:RunInstances")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 3

    def test_get_federation_token_awards_2(self):
        ctx = _ctx(events=[_event("sts:GetFederationToken")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 2

    def test_assume_role_with_web_identity_awards_2(self):
        ctx = _ctx(events=[_event("sts:AssumeRoleWithWebIdentity")])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 2

    def test_all_indicators_capped_at_10(self):
        ctx = _ctx(events=[
            _event("sts:AssumeRole", {"roleArn": OTHER_ACCOUNT_ROLE}),
            _event("ec2:RunInstances"),
            _event("sts:GetFederationToken"),
        ])
        result = self.rule.calculate(IDENTITY_ARN, ctx)
        assert result == 10

    def test_output_never_exceeds_max_contribution(self):
        ctx = _ctx(events=[
            _event("sts:AssumeRole", {"roleArn": OTHER_ACCOUNT_ROLE}),
            _event("ec2:RunInstances"),
            _event("sts:GetFederationToken"),
            _event("sts:AssumeRoleWithWebIdentity"),
        ])
        assert self.rule.calculate(IDENTITY_ARN, ctx) <= self.rule.max_contribution

    def test_cross_account_assume_role_only_awarded_once(self):
        """Multiple cross-account AssumeRole events should only award +5 once."""
        ctx = _ctx(events=[
            _event("sts:AssumeRole", {"roleArn": OTHER_ACCOUNT_ROLE}),
            _event("sts:AssumeRole", {"roleArn": "arn:aws:iam::888888888888:role/AnotherRole"}),
        ])
        assert self.rule.calculate(IDENTITY_ARN, ctx) == 5
