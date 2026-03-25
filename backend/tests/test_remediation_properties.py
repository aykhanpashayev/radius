"""Property-based tests for the Remediation_Engine using Hypothesis.

Validates formal correctness properties:
  - Rule serialization round-trip (Requirement 12.1)
  - Severity ordering invariant (Requirement 2.4 / Design Property 6)
  - Audit ID is UUID v4 (Requirement 12.4 / Design Property 4)
  - Monitor mode suppresses all actions (Requirement 1.2 / Design Property 5)
"""
from __future__ import annotations

import json
import re
import uuid
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from backend.functions.remediation_engine.actions.base import ActionOutcome
from backend.functions.remediation_engine.audit import write_audit_entry
from backend.functions.remediation_engine.engine import (
    RemediationRuleEngine,
    _SEVERITY_RANK,
    match_rules,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_SEVERITIES = list(_SEVERITY_RANK.keys())  # Low, Moderate, High, Very High, Critical
_VALID_ACTIONS = [
    "disable_iam_user",
    "remove_risky_policies",
    "block_role_assumption",
    "restrict_network_access",
    "notify_security_team",
]
_VALID_DETECTION_TYPES = [
    "privilege_escalation",
    "root_user_activity",
    "api_burst_anomaly",
    "cross_account_role_assumption",
    "iam_policy_modification_spike",
    "logging_disruption",
    "unusual_service_usage",
]
_VALID_IDENTITY_TYPES = ["IAMUser", "AssumedRole", "Root", "FederatedUser"]

_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

def valid_remediation_rule_strategy() -> st.SearchStrategy[dict[str, Any]]:
    """Generate dicts representing valid remediation rules.

    Produces rules with:
      - rule_id: non-empty string
      - name: non-empty string
      - active: bool
      - min_severity: one of the five valid severity levels
      - detection_types: list of zero or more valid detection type strings
      - identity_types: list of zero or more valid identity type strings
      - actions: non-empty list of valid action name strings
      - priority: integer 1–999
    """
    return st.fixed_dictionaries({
        "rule_id": st.uuids().map(str),
        "name": st.text(min_size=1, max_size=64).filter(lambda s: s.strip()),
        "active": st.booleans(),
        "min_severity": st.sampled_from(_VALID_SEVERITIES),
        "detection_types": st.lists(
            st.sampled_from(_VALID_DETECTION_TYPES), min_size=0, max_size=4, unique=True
        ),
        "identity_types": st.lists(
            st.sampled_from(_VALID_IDENTITY_TYPES), min_size=0, max_size=4, unique=True
        ),
        "actions": st.lists(
            st.sampled_from(_VALID_ACTIONS), min_size=1, max_size=5, unique=True
        ),
        "priority": st.integers(min_value=1, max_value=999),
    })


def valid_incident_strategy() -> st.SearchStrategy[dict[str, Any]]:
    """Generate dicts representing valid incidents for engine processing."""
    return st.fixed_dictionaries({
        "incident_id": st.uuids().map(str),
        "identity_arn": st.text(min_size=20, max_size=128).map(
            lambda s: f"arn:aws:iam::123456789012:user/{s[:32].strip() or 'x'}"
        ),
        "severity": st.sampled_from(_VALID_SEVERITIES),
        "detection_type": st.sampled_from(_VALID_DETECTION_TYPES),
        "identity_type": st.sampled_from(_VALID_IDENTITY_TYPES),
        "creation_timestamp": st.just("2024-01-01T00:00:00Z"),
    })


# ---------------------------------------------------------------------------
# Serialization helpers (mirrors how rules are stored/retrieved via DynamoDB JSON)
# ---------------------------------------------------------------------------

def _serialize_rule(rule: dict[str, Any]) -> str:
    """Serialize a rule dict to a JSON string (as stored in DynamoDB via API)."""
    return json.dumps(rule, sort_keys=True)


def _deserialize_rule(raw: str) -> dict[str, Any]:
    """Deserialize a JSON string back to a rule dict."""
    return json.loads(raw)


# ---------------------------------------------------------------------------
# Property 1: Rule serialization round-trip (Requirement 12.1)
# ---------------------------------------------------------------------------

@given(rule=valid_remediation_rule_strategy())
@settings(max_examples=200)
def test_rule_serialization_round_trip(rule: dict[str, Any]) -> None:
    """For any valid rule, deserialize(serialize(rule)) == rule.

    Validates that the JSON serialization used when persisting rules to
    DynamoDB and reading them back is lossless for all valid rule shapes.
    """
    serialized = _serialize_rule(rule)
    recovered = _deserialize_rule(serialized)
    assert recovered == rule, (
        f"Round-trip failed.\nOriginal:   {rule}\nRecovered:  {recovered}"
    )


# ---------------------------------------------------------------------------
# Property 2: Severity ordering invariant (Requirement 2.4 / Design Property 6)
# ---------------------------------------------------------------------------

@given(
    rule_base=valid_remediation_rule_strategy(),
    incident=valid_incident_strategy(),
    severity_a=st.sampled_from(_VALID_SEVERITIES),
    severity_b=st.sampled_from(_VALID_SEVERITIES),
)
@settings(max_examples=300)
def test_severity_ordering_invariant(
    rule_base: dict[str, Any],
    incident: dict[str, Any],
    severity_a: str,
    severity_b: str,
) -> None:
    """For any two severity levels A > B, any incident matched by a rule with
    min_severity=A is also matched by a rule with min_severity=B.

    Formally: rank(A) > rank(B) ∧ match(rule_A, incident) → match(rule_B, incident)

    This validates the monotonicity of the severity threshold: a stricter
    threshold (higher rank) matching implies a looser threshold also matches.
    """
    rank_a = _SEVERITY_RANK[severity_a]
    rank_b = _SEVERITY_RANK[severity_b]

    # Only test pairs where A is strictly more severe than B
    assume(rank_a > rank_b)

    # Build two otherwise-identical active rules differing only in min_severity.
    # Clear detection_types and identity_types so only severity governs matching.
    rule_a = {**rule_base, "active": True, "min_severity": severity_a,
              "detection_types": [], "identity_types": []}
    rule_b = {**rule_base, "active": True, "min_severity": severity_b,
              "detection_types": [], "identity_types": []}

    matched_a = match_rules([rule_a], incident)
    matched_b = match_rules([rule_b], incident)

    if matched_a:
        # If the stricter rule matched, the looser rule must also match
        assert matched_b, (
            f"Severity ordering violated: rule with min_severity={severity_a!r} "
            f"(rank {rank_a}) matched incident severity={incident['severity']!r}, "
            f"but rule with min_severity={severity_b!r} (rank {rank_b}) did not."
        )


# ---------------------------------------------------------------------------
# Property 3: Audit ID is UUID v4 (Requirement 12.4 / Design Property 4)
# ---------------------------------------------------------------------------

@given(
    incident=valid_incident_strategy(),
    rule_id=st.uuids().map(str),
    action_name=st.sampled_from(_VALID_ACTIONS),
    outcome_value=st.sampled_from(["executed", "skipped", "failed", "suppressed"]),
    risk_mode=st.sampled_from(["monitor", "alert", "enforce"]),
    dry_run=st.booleans(),
    reason=st.one_of(st.none(), st.text(min_size=1, max_size=64)),
)
@settings(max_examples=200)
def test_audit_id_is_uuid4(
    incident: dict[str, Any],
    rule_id: str,
    action_name: str,
    outcome_value: str,
    risk_mode: str,
    dry_run: bool,
    reason: str | None,
) -> None:
    """For any audit entry written by write_audit_entry(), the audit_id field
    matches the UUID v4 regex pattern.

    Validates that audit IDs are always well-formed UUID v4 values regardless
    of the input combination, ensuring audit log integrity and uniqueness.
    """
    outcome = ActionOutcome(
        action_name=action_name,
        outcome=outcome_value,
        reason=reason,
        details={},
    )

    captured: dict[str, Any] = {}

    def fake_put(table: str, item: dict[str, Any]) -> None:
        captured["item"] = item

    with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
        write_audit_entry(
            "audit-table", incident, rule_id, action_name, outcome, risk_mode, dry_run
        )

    audit_id = captured["item"]["audit_id"]
    assert _UUID4_RE.match(audit_id), (
        f"audit_id {audit_id!r} is not a valid UUID v4"
    )
    # Also verify it parses as a real UUID object with version=4
    parsed = uuid.UUID(audit_id)
    assert parsed.version == 4, f"UUID version is {parsed.version}, expected 4"


# ---------------------------------------------------------------------------
# Property 4: Monitor mode suppresses all actions (Requirement 1.2 / Design Property 5)
# ---------------------------------------------------------------------------

@given(
    incident=valid_incident_strategy(),
    rules=st.lists(valid_remediation_rule_strategy(), min_size=1, max_size=5),
)
@settings(max_examples=200)
def test_monitor_mode_suppresses_all_actions(
    incident: dict[str, Any],
    rules: list[dict[str, Any]],
) -> None:
    """For any incident and any rule configuration, when risk_mode=monitor,
    all ActionOutcome.outcome values in the result equal 'suppressed'.

    This is the core safety guarantee of monitor mode: the engine must never
    mutate AWS state when operating in monitor mode, which is enforced by
    ensuring every action outcome is 'suppressed'.
    """
    # Force all rules active so we always exercise the action path
    active_rules = [{**r, "active": True} for r in rules]

    config = {
        "risk_mode": "monitor",
        "rules": active_rules,
        "excluded_arns": [],
        "protected_account_ids": [],
        "allowed_ip_ranges": [],
    }

    engine = RemediationRuleEngine(
        config_table="cfg-table",
        audit_table="audit-table",
        topic_arn="arn:aws:sns:us-east-1:123:topic",
        dry_run=False,
    )

    # Build a mock action whose suppress() returns a proper suppressed outcome
    # and whose execute() must never be called in monitor mode
    mock_action = MagicMock()
    mock_action.suppress.side_effect = lambda arn, inc, reason: ActionOutcome(
        action_name="mock_action",
        outcome="suppressed",
        reason=reason,
        details={},
    )
    mock_action.execute.side_effect = AssertionError(
        "execute() must never be called in monitor mode"
    )

    mock_all_actions = {name: mock_action for name in _VALID_ACTIONS}

    with patch("backend.functions.remediation_engine.engine.load_config", return_value=config), \
         patch("backend.functions.remediation_engine.safety.check_safety_controls", return_value=None), \
         patch("backend.functions.remediation_engine.engine.ALL_ACTIONS", mock_all_actions), \
         patch("backend.functions.remediation_engine.audit.write_audit_entry"), \
         patch("backend.functions.remediation_engine.audit.write_audit_summary"), \
         patch("backend.functions.remediation_engine.audit.write_audit_no_match"), \
         patch("backend.functions.remediation_engine.audit.write_audit_suppressed"):
        result = engine.process(incident)

    # If any rules matched, every action outcome must be suppressed
    action_outcomes = result.get("action_outcomes", [])
    if action_outcomes:
        non_suppressed = [
            o for o in action_outcomes if o["outcome"] != "suppressed"
        ]
        assert not non_suppressed, (
            f"Monitor mode produced non-suppressed outcomes: {non_suppressed}\n"
            f"Full result: {result}"
        )

    # The engine must never report executed > 0 in monitor mode
    assert result["executed"] == 0, (
        f"Monitor mode reported {result['executed']} executed actions — expected 0"
    )
