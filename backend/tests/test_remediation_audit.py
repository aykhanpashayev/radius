"""Unit tests for remediation_engine/audit.py."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, call, patch

import pytest

from backend.functions.remediation_engine.actions.base import ActionOutcome
from backend.functions.remediation_engine.audit import (
    write_audit_entry,
    write_audit_no_match,
    write_audit_summary,
    write_audit_suppressed,
)

_AUDIT_TABLE = "remediation-audit-test"
_UUID4_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_REQUIRED_FIELDS = {
    "audit_id", "incident_id", "identity_arn", "rule_id",
    "action_name", "outcome", "risk_mode", "dry_run",
    "timestamp", "details", "reason", "ttl",
}

_INCIDENT = {
    "incident_id": "inc-001",
    "identity_arn": "arn:aws:iam::123456789012:user/alice",
    "detection_type": "privilege_escalation",
    "severity": "High",
}

_OUTCOME = ActionOutcome(
    action_name="disable_iam_user",
    outcome="executed",
    reason=None,
    details={"deactivated_key_ids": ["AKIA1"]},
)


def _capture_put_item():
    """Return a mock that captures the item passed to put_item."""
    captured = {}

    def fake_put(audit_table, item):
        captured["item"] = item

    return fake_put, captured


# ---------------------------------------------------------------------------
# write_audit_entry — audit_id is UUID v4
# ---------------------------------------------------------------------------

class TestWriteAuditEntryAuditId:
    def test_audit_id_is_valid_uuid4(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        audit_id = captured["item"]["audit_id"]
        assert _UUID4_RE.match(audit_id), f"Not a valid UUID v4: {audit_id}"

    def test_each_call_produces_unique_audit_id(self):
        ids = []

        def capture_put(table, item):
            ids.append(item["audit_id"])

        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=capture_put):
            for _ in range(5):
                write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        assert len(set(ids)) == 5


# ---------------------------------------------------------------------------
# write_audit_entry — TTL is ~365 days from now
# ---------------------------------------------------------------------------

class TestWriteAuditEntryTTL:
    def test_ttl_is_approximately_365_days_from_now(self):
        fake_put, captured = _capture_put_item()
        before = int(datetime.now(tz=timezone.utc).timestamp())

        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        after = int(datetime.now(tz=timezone.utc).timestamp())
        ttl = captured["item"]["ttl"]

        expected_min = before + 365 * 86400
        expected_max = after + 365 * 86400 + 60  # 60-second tolerance

        assert expected_min <= ttl <= expected_max, (
            f"TTL {ttl} not within expected range [{expected_min}, {expected_max}]"
        )


# ---------------------------------------------------------------------------
# write_audit_entry — all required fields present
# ---------------------------------------------------------------------------

class TestWriteAuditEntryRequiredFields:
    def test_all_required_fields_present(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        item = captured["item"]
        missing = _REQUIRED_FIELDS - set(item.keys())
        assert not missing, f"Missing fields: {missing}"

    def test_fields_have_correct_values(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        item = captured["item"]
        assert item["incident_id"] == "inc-001"
        assert item["identity_arn"] == "arn:aws:iam::123456789012:user/alice"
        assert item["rule_id"] == "rule-1"
        assert item["action_name"] == "disable_iam_user"
        assert item["outcome"] == "executed"
        assert item["risk_mode"] == "enforce"
        assert item["dry_run"] is False

    def test_details_is_json_string(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        details = captured["item"]["details"]
        assert isinstance(details, str)
        parsed = json.loads(details)
        assert parsed == {"deactivated_key_ids": ["AKIA1"]}

    def test_reason_is_empty_string_when_none(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)

        assert captured["item"]["reason"] == ""

    def test_reason_populated_when_set(self):
        outcome = ActionOutcome(
            action_name="disable_iam_user",
            outcome="skipped",
            reason="identity_type_not_supported",
        )
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", outcome, "enforce", False)

        assert captured["item"]["reason"] == "identity_type_not_supported"

    def test_dry_run_flag_stored(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "monitor", True)

        assert captured["item"]["dry_run"] is True
        assert captured["item"]["risk_mode"] == "monitor"


# ---------------------------------------------------------------------------
# write_audit_summary
# ---------------------------------------------------------------------------

class TestWriteAuditSummary:
    def test_summary_action_name_is_remediation_complete(self):
        fake_put, captured = _capture_put_item()
        outcomes = [
            ActionOutcome("disable_iam_user", "executed", None),
            ActionOutcome("notify_security_team", "suppressed", "monitor_mode"),
        ]
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_summary(_AUDIT_TABLE, _INCIDENT, outcomes, "enforce", False)

        assert captured["item"]["action_name"] == "remediation_complete"
        assert captured["item"]["outcome"] == "summary"

    def test_summary_counts_are_correct(self):
        fake_put, captured = _capture_put_item()
        outcomes = [
            ActionOutcome("a", "executed", None),
            ActionOutcome("b", "executed", None),
            ActionOutcome("c", "skipped", "no_match"),
            ActionOutcome("d", "failed", "error"),
            ActionOutcome("e", "suppressed", "monitor_mode"),
        ]
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_summary(_AUDIT_TABLE, _INCIDENT, outcomes, "enforce", False)

        counts = json.loads(captured["item"]["details"])
        assert counts["executed"] == 2
        assert counts["skipped"] == 1
        assert counts["failed"] == 1
        assert counts["suppressed"] == 1

    def test_summary_has_valid_uuid4_audit_id(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_summary(_AUDIT_TABLE, _INCIDENT, [], "monitor", False)

        assert _UUID4_RE.match(captured["item"]["audit_id"])


# ---------------------------------------------------------------------------
# write_audit_suppressed
# ---------------------------------------------------------------------------

class TestWriteAuditSuppressed:
    def test_writes_suppressed_outcome(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_suppressed(_AUDIT_TABLE, _INCIDENT, "identity_excluded", "monitor", False)

        item = captured["item"]
        assert item["outcome"] == "suppressed"
        assert item["reason"] == "identity_excluded"
        assert item["action_name"] == "remediation_suppressed"


# ---------------------------------------------------------------------------
# write_audit_no_match
# ---------------------------------------------------------------------------

class TestWriteAuditNoMatch:
    def test_writes_skipped_outcome(self):
        fake_put, captured = _capture_put_item()
        with patch("backend.functions.remediation_engine.audit._put_item", side_effect=fake_put):
            write_audit_no_match(_AUDIT_TABLE, _INCIDENT, "enforce", False)

        item = captured["item"]
        assert item["outcome"] == "skipped"
        assert item["reason"] == "no_rules_matched"
        assert item["action_name"] == "no_rules_matched"


# ---------------------------------------------------------------------------
# _put_item swallows errors non-fatally
# ---------------------------------------------------------------------------

class TestPutItemNonFatal:
    def test_dynamodb_error_does_not_raise(self):
        with patch("boto3.resource") as mock_boto:
            mock_table = MagicMock()
            mock_table.put_item.side_effect = Exception("DynamoDB unavailable")
            mock_boto.return_value.Table.return_value = mock_table

            # Should not raise
            write_audit_entry(_AUDIT_TABLE, _INCIDENT, "rule-1", "disable_iam_user", _OUTCOME, "enforce", False)
