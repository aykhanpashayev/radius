"""Unit tests for remediation_engine/engine.py — rule matching and deduplication."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.functions.remediation_engine.engine import (
    RemediationRuleEngine,
    deduplicate_actions,
    match_rules,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rule(
    rule_id: str = "r1",
    min_severity: str = "Low",
    detection_types: list | None = None,
    identity_types: list | None = None,
    actions: list | None = None,
    active: bool = True,
    priority: int = 10,
) -> dict:
    return {
        "rule_id": rule_id,
        "active": active,
        "min_severity": min_severity,
        "detection_types": detection_types if detection_types is not None else [],
        "identity_types": identity_types if identity_types is not None else [],
        "actions": actions if actions is not None else ["notify_security_team"],
        "priority": priority,
    }


def _incident(
    severity: str = "High",
    detection_type: str = "privilege_escalation",
    identity_type: str = "IAMUser",
) -> dict:
    return {
        "incident_id": "inc-001",
        "identity_arn": "arn:aws:iam::123456789012:user/alice",
        "severity": severity,
        "detection_type": detection_type,
        "identity_type": identity_type,
    }


# ---------------------------------------------------------------------------
# match_rules — min_severity threshold
# ---------------------------------------------------------------------------

class TestMatchRulesMinSeverity:
    def test_exact_severity_matches(self):
        rules = [_rule(min_severity="High")]
        result = match_rules(rules, _incident(severity="High"))
        assert len(result) == 1

    def test_higher_severity_matches(self):
        rules = [_rule(min_severity="High")]
        result = match_rules(rules, _incident(severity="Critical"))
        assert len(result) == 1

    def test_lower_severity_does_not_match(self):
        rules = [_rule(min_severity="High")]
        result = match_rules(rules, _incident(severity="Low"))
        assert result == []

    def test_moderate_below_high_does_not_match(self):
        rules = [_rule(min_severity="High")]
        result = match_rules(rules, _incident(severity="Moderate"))
        assert result == []

    def test_all_severities_match_low_threshold(self):
        rules = [_rule(min_severity="Low")]
        for sev in ("Low", "Moderate", "High", "Very High", "Critical"):
            assert match_rules(rules, _incident(severity=sev)) != []

    def test_only_critical_matches_critical_threshold(self):
        rules = [_rule(min_severity="Critical")]
        assert match_rules(rules, _incident(severity="Very High")) == []
        assert match_rules(rules, _incident(severity="Critical")) != []

    def test_inactive_rule_never_matches(self):
        rules = [_rule(min_severity="Low", active=False)]
        assert match_rules(rules, _incident(severity="Critical")) == []


# ---------------------------------------------------------------------------
# match_rules — detection_types filter
# ---------------------------------------------------------------------------

class TestMatchRulesDetectionTypes:
    def test_empty_detection_types_matches_all(self):
        rules = [_rule(detection_types=[])]
        assert match_rules(rules, _incident(detection_type="anything")) != []

    def test_matching_detection_type_passes(self):
        rules = [_rule(detection_types=["privilege_escalation"])]
        assert match_rules(rules, _incident(detection_type="privilege_escalation")) != []

    def test_non_matching_detection_type_filtered(self):
        rules = [_rule(detection_types=["privilege_escalation"])]
        assert match_rules(rules, _incident(detection_type="root_user_activity")) == []

    def test_multiple_detection_types_any_match(self):
        rules = [_rule(detection_types=["privilege_escalation", "root_user_activity"])]
        assert match_rules(rules, _incident(detection_type="root_user_activity")) != []


# ---------------------------------------------------------------------------
# match_rules — identity_types filter
# ---------------------------------------------------------------------------

class TestMatchRulesIdentityTypes:
    def test_empty_identity_types_matches_all(self):
        rules = [_rule(identity_types=[])]
        assert match_rules(rules, _incident(identity_type="AssumedRole")) != []

    def test_matching_identity_type_passes(self):
        rules = [_rule(identity_types=["IAMUser"])]
        assert match_rules(rules, _incident(identity_type="IAMUser")) != []

    def test_non_matching_identity_type_filtered(self):
        rules = [_rule(identity_types=["IAMUser"])]
        assert match_rules(rules, _incident(identity_type="AssumedRole")) == []


# ---------------------------------------------------------------------------
# match_rules — ordering
# ---------------------------------------------------------------------------

class TestMatchRulesOrdering:
    def test_rules_sorted_by_priority(self):
        r_low = _rule(rule_id="low-pri", priority=20)
        r_high = _rule(rule_id="high-pri", priority=5)
        result = match_rules([r_low, r_high], _incident())
        assert result[0]["rule_id"] == "high-pri"
        assert result[1]["rule_id"] == "low-pri"


# ---------------------------------------------------------------------------
# deduplicate_actions
# ---------------------------------------------------------------------------

class TestDeduplicateActions:
    def test_no_duplicates_unchanged(self):
        assert deduplicate_actions(["a", "b", "c"]) == ["a", "b", "c"]

    def test_duplicates_removed_first_occurrence_kept(self):
        assert deduplicate_actions(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]

    def test_empty_list(self):
        assert deduplicate_actions([]) == []

    def test_all_same(self):
        assert deduplicate_actions(["x", "x", "x"]) == ["x"]


# ---------------------------------------------------------------------------
# RemediationRuleEngine.process — no-match path
# ---------------------------------------------------------------------------

class TestEngineNoMatchPath:
    def _make_engine(self):
        return RemediationRuleEngine(
            config_table="cfg-table",
            audit_table="audit-table",
            topic_arn="arn:aws:sns:us-east-1:123:topic",
        )

    def test_no_match_writes_audit_entry(self):
        engine = self._make_engine()
        config = {
            "risk_mode": "enforce",
            "rules": [],
            "excluded_arns": [],
            "protected_account_ids": [],
            "allowed_ip_ranges": [],
        }
        with patch("backend.functions.remediation_engine.engine.load_config", return_value=config), \
             patch("backend.functions.remediation_engine.safety.check_safety_controls", return_value=None), \
             patch("backend.functions.remediation_engine.audit.write_audit_no_match") as mock_no_match, \
             patch("backend.functions.remediation_engine.audit.write_audit_entry"), \
             patch("backend.functions.remediation_engine.audit.write_audit_summary"), \
             patch("backend.functions.remediation_engine.audit.write_audit_suppressed"):
            result = engine.process(_incident())

        mock_no_match.assert_called_once()
        assert result["matched_rules"] == []

    def test_multiple_matched_rules_deduplicate_actions(self):
        engine = self._make_engine()
        rules = [
            _rule(rule_id="r1", actions=["disable_iam_user", "notify_security_team"], priority=1),
            _rule(rule_id="r2", actions=["notify_security_team", "restrict_network_access"], priority=2),
        ]
        config = {
            "risk_mode": "monitor",
            "rules": rules,
            "excluded_arns": [],
            "protected_account_ids": [],
            "allowed_ip_ranges": [],
        }

        mock_action = MagicMock()
        mock_action.suppress.return_value = MagicMock(
            action_name="x", outcome="suppressed", reason="monitor_mode", details={}
        )

        with patch("backend.functions.remediation_engine.engine.load_config", return_value=config), \
             patch("backend.functions.remediation_engine.safety.check_safety_controls", return_value=None), \
             patch("backend.functions.remediation_engine.audit.write_audit_entry"), \
             patch("backend.functions.remediation_engine.audit.write_audit_summary"), \
             patch("backend.functions.remediation_engine.audit.write_audit_no_match"), \
             patch("backend.functions.remediation_engine.audit.write_audit_suppressed"), \
             patch("backend.functions.remediation_engine.engine.ALL_ACTIONS", {
                 "disable_iam_user": mock_action,
                 "notify_security_team": mock_action,
                 "restrict_network_access": mock_action,
             }):
            result = engine.process(_incident())

        # 3 unique actions across 2 rules (notify_security_team deduplicated)
        assert mock_action.suppress.call_count == 3
        assert result["matched_rules"] == ["r1", "r2"]
