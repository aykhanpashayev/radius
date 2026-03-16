"""Unit tests for all 7 detection rules."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.interfaces import Finding
from backend.functions.detection_engine.rules.privilege_escalation import PrivilegeEscalationRule
from backend.functions.detection_engine.rules.iam_policy_modification_spike import IAMPolicyModificationSpikeRule
from backend.functions.detection_engine.rules.cross_account_role_assumption import CrossAccountRoleAssumptionRule
from backend.functions.detection_engine.rules.logging_disruption import LoggingDisruptionRule
from backend.functions.detection_engine.rules.root_user_activity import RootUserActivityRule
from backend.functions.detection_engine.rules.api_burst_anomaly import APIBurstAnomalyRule
from backend.functions.detection_engine.rules.unusual_service_usage import UnusualServiceUsageRule

_IDENTITY = "arn:aws:iam::111111111111:user/alice"
_ROLE_SAME = "arn:aws:iam::111111111111:role/MyRole"
_ROLE_CROSS = "arn:aws:iam::999999999999:role/CrossRole"


def _event(event_type: str, identity_arn: str = _IDENTITY, **kwargs) -> dict:
    return {
        "event_id": "evt-001",
        "event_type": event_type,
        "identity_arn": identity_arn,
        "identity_type": "IAMUser",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_parameters": {},
        **kwargs,
    }


def _ctx(recent_60m: list[dict] | None = None, prior_services: set[str] | None = None) -> DetectionContext:
    return DetectionContext(
        identity_arn=_IDENTITY,
        recent_events_60m=recent_60m or [],
        prior_services_30d=prior_services or set(),
    )


def _recent_event(event_type: str, minutes_ago: int = 10) -> dict:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {"event_id": f"hist-{minutes_ago}", "event_type": event_type, "timestamp": ts}


# ===========================================================================
# Rule 1 — PrivilegeEscalation
# ===========================================================================

class TestPrivilegeEscalationRule:
    rule = PrivilegeEscalationRule()

    def test_no_trigger_on_unrelated_event(self):
        assert self.rule.evaluate_with_context(_event("iam:ListUsers"), _ctx()) is None

    @pytest.mark.parametrize("action", ["CreatePolicyVersion", "AddUserToGroup", "PassRole"])
    def test_triggers_on_direct_escalation_events(self, action):
        finding = self.rule.evaluate_with_context(_event(f"iam:{action}"), _ctx())
        assert finding is not None
        assert finding.detection_type == "privilege_escalation"
        assert finding.severity == "High"
        assert finding.confidence == 80
        assert action in finding.description

    def test_triggers_on_attach_user_policy_with_recent_create_user(self):
        ctx = _ctx(recent_60m=[_recent_event("iam:CreateUser")])
        finding = self.rule.evaluate_with_context(_event("iam:AttachUserPolicy"), ctx)
        assert finding is not None
        assert "CreateUser" in finding.description
        assert "AttachUserPolicy" in finding.description

    def test_no_trigger_on_attach_user_policy_without_recent_create_user(self):
        ctx = _ctx(recent_60m=[_recent_event("iam:ListUsers")])
        assert self.rule.evaluate_with_context(_event("iam:AttachUserPolicy"), ctx) is None

    def test_finding_contains_event_id(self):
        ev = _event("iam:PassRole")
        ev["event_id"] = "specific-id"
        finding = self.rule.evaluate_with_context(ev, _ctx())
        assert "specific-id" in finding.related_event_ids


# ===========================================================================
# Rule 2 — IAMPolicyModificationSpike
# ===========================================================================

class TestIAMPolicyModificationSpikeRule:
    rule = IAMPolicyModificationSpikeRule()

    def test_no_trigger_below_threshold(self):
        ctx = _ctx(recent_60m=[_recent_event("iam:AttachUserPolicy") for _ in range(4)])
        assert self.rule.evaluate_with_context(_event("iam:AttachUserPolicy"), ctx) is None

    def test_triggers_at_threshold(self):
        ctx = _ctx(recent_60m=[_recent_event("iam:AttachRolePolicy") for _ in range(5)])
        finding = self.rule.evaluate_with_context(_event("iam:AttachRolePolicy"), ctx)
        assert finding is not None
        assert finding.detection_type == "iam_policy_modification_spike"
        assert finding.severity == "High"
        assert finding.confidence == 75
        assert "5" in finding.description

    def test_triggers_above_threshold(self):
        ctx = _ctx(recent_60m=[_recent_event("iam:PutRolePolicy") for _ in range(10)])
        finding = self.rule.evaluate_with_context(_event("iam:PutRolePolicy"), ctx)
        assert finding is not None
        assert "10" in finding.description

    def test_counts_only_mutation_events(self):
        # Mix of mutation and non-mutation events — only 3 mutations
        events = (
            [_recent_event("iam:AttachUserPolicy")] * 3
            + [_recent_event("iam:ListUsers")] * 10
        )
        ctx = _ctx(recent_60m=events)
        assert self.rule.evaluate_with_context(_event("iam:ListUsers"), ctx) is None

    @pytest.mark.parametrize("action", [
        "AttachUserPolicy", "AttachRolePolicy", "AttachGroupPolicy",
        "PutUserPolicy", "PutRolePolicy", "PutGroupPolicy",
        "CreatePolicyVersion", "SetDefaultPolicyVersion", "AddUserToGroup",
    ])
    def test_all_mutation_events_counted(self, action):
        ctx = _ctx(recent_60m=[_recent_event(f"iam:{action}") for _ in range(5)])
        finding = self.rule.evaluate_with_context(_event(f"iam:{action}"), ctx)
        assert finding is not None


# ===========================================================================
# Rule 3 — CrossAccountRoleAssumption
# ===========================================================================

class TestCrossAccountRoleAssumptionRule:
    rule = CrossAccountRoleAssumptionRule()

    def test_no_trigger_on_non_assume_role(self):
        assert self.rule.evaluate(_event("iam:CreateUser")) is None

    def test_no_trigger_on_same_account_assume_role(self):
        ev = _event("sts:AssumeRole", event_parameters={"roleArn": _ROLE_SAME})
        assert self.rule.evaluate(ev) is None

    def test_triggers_on_cross_account_assume_role(self):
        ev = _event("sts:AssumeRole", event_parameters={"roleArn": _ROLE_CROSS})
        finding = self.rule.evaluate(ev)
        assert finding is not None
        assert finding.detection_type == "cross_account_role_assumption"
        assert finding.severity == "Moderate"
        assert finding.confidence == 70
        assert "111111111111" in finding.description
        assert "999999999999" in finding.description

    def test_no_trigger_when_role_arn_missing(self):
        ev = _event("sts:AssumeRole", event_parameters={})
        assert self.rule.evaluate(ev) is None

    def test_no_trigger_when_identity_account_not_extractable(self):
        ev = _event("sts:AssumeRole", identity_arn="arn:aws:iam:::user/alice",
                    event_parameters={"roleArn": _ROLE_CROSS})
        assert self.rule.evaluate(ev) is None


# ===========================================================================
# Rule 4 — LoggingDisruption
# ===========================================================================

class TestLoggingDisruptionRule:
    rule = LoggingDisruptionRule()

    def test_no_trigger_on_unrelated_event(self):
        assert self.rule.evaluate(_event("iam:CreateUser")) is None

    @pytest.mark.parametrize("action", [
        "StopLogging", "DeleteTrail", "UpdateTrail", "PutEventSelectors",
        "DeleteFlowLogs", "DeleteLogGroup", "DeleteLogStream",
    ])
    def test_triggers_on_all_disruption_events(self, action):
        finding = self.rule.evaluate(_event(f"cloudtrail:{action}"))
        assert finding is not None
        assert finding.detection_type == "logging_disruption"
        assert finding.severity == "Critical"
        assert finding.confidence == 95
        assert action in finding.description

    def test_finding_identity_arn_matches_event(self):
        finding = self.rule.evaluate(_event("cloudtrail:StopLogging"))
        assert finding.identity_arn == _IDENTITY


# ===========================================================================
# Rule 5 — RootUserActivity
# ===========================================================================

class TestRootUserActivityRule:
    rule = RootUserActivityRule()

    def test_no_trigger_on_regular_iam_user(self):
        assert self.rule.evaluate(_event("iam:CreateUser")) is None

    def test_triggers_on_identity_type_root(self):
        ev = _event("iam:CreateUser", identity_type="Root")
        finding = self.rule.evaluate(ev)
        assert finding is not None
        assert finding.detection_type == "root_user_activity"
        assert finding.severity == "Very High"
        assert finding.confidence == 100
        assert "Root" in finding.description or "root" in finding.description.lower()

    def test_triggers_on_root_arn_fallback(self):
        ev = _event("iam:CreateUser",
                    identity_arn="arn:aws:iam::123456789012:root")
        finding = self.rule.evaluate(ev)
        assert finding is not None
        assert finding.detection_type == "root_user_activity"

    def test_identity_type_takes_priority_over_arn(self):
        # Both conditions true — should still return a finding (not double-fire)
        ev = _event("iam:CreateUser",
                    identity_arn="arn:aws:iam::123456789012:root",
                    identity_type="Root")
        finding = self.rule.evaluate(ev)
        assert finding is not None
        # Primary check description (no ARN-based suffix)
        assert "ARN-based" not in finding.description

    def test_no_trigger_on_user_with_root_in_name(self):
        # "root" in username should NOT trigger — only in the :root position
        ev = _event("iam:CreateUser",
                    identity_arn="arn:aws:iam::123456789012:user/groot")
        assert self.rule.evaluate(ev) is None


# ===========================================================================
# Rule 6 — APIBurstAnomaly
# ===========================================================================

class TestAPIBurstAnomalyRule:
    rule = APIBurstAnomalyRule()

    def _ctx_with_5m_events(self, count: int) -> DetectionContext:
        now = datetime.now(timezone.utc)
        events = [
            {
                "event_id": f"e{i}",
                "event_type": "iam:ListUsers",
                "timestamp": (now - timedelta(minutes=2)).isoformat(),
            }
            for i in range(count)
        ]
        return DetectionContext(identity_arn=_IDENTITY, recent_events_60m=events)

    def test_no_trigger_below_threshold(self):
        ctx = self._ctx_with_5m_events(19)
        assert self.rule.evaluate_with_context(_event("iam:ListUsers"), ctx) is None

    def test_triggers_at_threshold(self):
        ctx = self._ctx_with_5m_events(20)
        finding = self.rule.evaluate_with_context(_event("iam:ListUsers"), ctx)
        assert finding is not None
        assert finding.detection_type == "api_burst_anomaly"
        assert finding.severity == "Moderate"
        assert finding.confidence == 65
        assert "20" in finding.description
        assert "5 minutes" in finding.description

    def test_triggers_above_threshold(self):
        ctx = self._ctx_with_5m_events(50)
        finding = self.rule.evaluate_with_context(_event("iam:ListUsers"), ctx)
        assert finding is not None
        assert "50" in finding.description

    def test_no_trigger_when_events_older_than_5m(self):
        now = datetime.now(timezone.utc)
        old_events = [
            {
                "event_id": f"e{i}",
                "event_type": "iam:ListUsers",
                "timestamp": (now - timedelta(minutes=30)).isoformat(),
            }
            for i in range(25)
        ]
        ctx = DetectionContext(identity_arn=_IDENTITY, recent_events_60m=old_events)
        assert self.rule.evaluate_with_context(_event("iam:ListUsers"), ctx) is None


# ===========================================================================
# Rule 7 — UnusualServiceUsage
# ===========================================================================

class TestUnusualServiceUsageRule:
    rule = UnusualServiceUsageRule()

    def test_no_trigger_when_service_seen_before(self):
        ctx = _ctx(prior_services={"iam"})
        assert self.rule.evaluate_with_context(_event("iam:CreateUser"), ctx) is None

    def test_no_trigger_on_non_high_risk_service(self):
        ctx = _ctx(prior_services=set())
        assert self.rule.evaluate_with_context(_event("ec2:DescribeInstances"), ctx) is None

    @pytest.mark.parametrize("service", ["sts", "iam", "organizations", "kms", "secretsmanager", "ssm"])
    def test_triggers_on_first_use_of_high_risk_service(self, service):
        ctx = _ctx(prior_services=set())
        finding = self.rule.evaluate_with_context(_event(f"{service}:SomeAction"), ctx)
        assert finding is not None
        assert finding.detection_type == "unusual_service_usage"
        assert finding.severity == "Low"
        assert finding.confidence == 60
        assert service in finding.description

    def test_no_trigger_when_event_type_has_no_colon(self):
        ctx = _ctx(prior_services=set())
        assert self.rule.evaluate_with_context(_event("UnknownEvent"), ctx) is None

    def test_service_comparison_is_case_insensitive(self):
        # event_type with uppercase service prefix
        ctx = _ctx(prior_services=set())
        finding = self.rule.evaluate_with_context(_event("IAM:CreateUser"), ctx)
        # "IAM".lower() == "iam" which is in HIGH_RISK_SERVICES
        assert finding is not None
