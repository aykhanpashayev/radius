"""Unit tests for remediation_engine/safety.py — each control in isolation."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.functions.remediation_engine.safety import (
    _extract_account_id,
    _query_recent_executions,
    check_safety_controls,
)

_USER_ARN = "arn:aws:iam::123456789012:user/alice"
_ROLE_ARN = "arn:aws:iam::123456789012:role/my-role"
_AUDIT_TABLE = "remediation-audit-test"


def _config(
    excluded_arns: list | None = None,
    protected_account_ids: list | None = None,
) -> dict:
    return {
        "excluded_arns": excluded_arns or [],
        "protected_account_ids": protected_account_ids or [],
    }


# ---------------------------------------------------------------------------
# _extract_account_id
# ---------------------------------------------------------------------------

class TestExtractAccountId:
    def test_extracts_from_user_arn(self):
        assert _extract_account_id(_USER_ARN) == "123456789012"

    def test_extracts_from_role_arn(self):
        assert _extract_account_id(_ROLE_ARN) == "123456789012"

    def test_returns_none_for_malformed_arn(self):
        assert _extract_account_id("not-an-arn") is None

    def test_returns_none_for_empty_string(self):
        assert _extract_account_id("") is None


# ---------------------------------------------------------------------------
# excluded_arns control
# ---------------------------------------------------------------------------

class TestExcludedArns:
    def test_identity_in_excluded_arns_suppressed(self):
        config = _config(excluded_arns=[_USER_ARN])
        reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason == "identity_excluded"

    def test_identity_not_in_excluded_arns_passes(self):
        config = _config(excluded_arns=["arn:aws:iam::999:user/other"])
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=0):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None

    def test_empty_excluded_arns_passes(self):
        config = _config(excluded_arns=[])
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=0):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None


# ---------------------------------------------------------------------------
# protected_account_ids control
# ---------------------------------------------------------------------------

class TestProtectedAccountIds:
    def test_identity_in_protected_account_suppressed(self):
        config = _config(protected_account_ids=["123456789012"])
        reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason == "account_protected"

    def test_identity_in_different_account_passes(self):
        config = _config(protected_account_ids=["999999999999"])
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=0):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None

    def test_empty_protected_accounts_passes(self):
        config = _config(protected_account_ids=[])
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=0):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None


# ---------------------------------------------------------------------------
# Cooldown control (60-minute window)
# ---------------------------------------------------------------------------

class TestCooldownControl:
    def test_recent_execution_within_60_min_suppressed(self):
        config = _config()
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=1):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason == "cooldown_active"

    def test_no_recent_executions_passes_cooldown(self):
        config = _config()
        # First call (1h window) returns 0, second call (24h window) also 0
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=0):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None

    def test_cooldown_checked_before_rate_limit(self):
        """Cooldown fires first — rate limit query should not be reached."""
        config = _config()
        call_counts = []

        def fake_query(table, arn, hours):
            call_counts.append(hours)
            # First call is 1h (cooldown) — return 1 to trigger suppression
            return 1 if hours == 1 else 0

        with patch("backend.functions.remediation_engine.safety._query_recent_executions", side_effect=fake_query):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)

        assert reason == "cooldown_active"
        # Only the 1h cooldown query should have been made
        assert call_counts == [1]


# ---------------------------------------------------------------------------
# Rate limit control (24-hour, max 10)
# ---------------------------------------------------------------------------

class TestRateLimitControl:
    def test_exactly_10_executions_in_24h_suppressed(self):
        config = _config()

        def fake_query(table, arn, hours):
            return 0 if hours == 1 else 10  # cooldown clear, rate limit hit

        with patch("backend.functions.remediation_engine.safety._query_recent_executions", side_effect=fake_query):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason == "rate_limit_exceeded"

    def test_9_executions_in_24h_passes(self):
        config = _config()

        def fake_query(table, arn, hours):
            return 0 if hours == 1 else 9

        with patch("backend.functions.remediation_engine.safety._query_recent_executions", side_effect=fake_query):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None

    def test_11_executions_in_24h_suppressed(self):
        config = _config()

        def fake_query(table, arn, hours):
            return 0 if hours == 1 else 11

        with patch("backend.functions.remediation_engine.safety._query_recent_executions", side_effect=fake_query):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason == "rate_limit_exceeded"


# ---------------------------------------------------------------------------
# Pass-through — no controls fire
# ---------------------------------------------------------------------------

class TestPassThrough:
    def test_all_controls_clear_returns_none(self):
        config = _config()
        with patch("backend.functions.remediation_engine.safety._query_recent_executions", return_value=0):
            reason = check_safety_controls(_USER_ARN, config, _AUDIT_TABLE)
        assert reason is None

    def test_query_failure_allows_remediation(self):
        """If DynamoDB query fails, safety check is non-fatal and allows proceed."""
        config = _config()
        with patch(
            "backend.functions.remediation_engine.safety._query_recent_executions",
            side_effect=Exception("DynamoDB unavailable"),
        ):
            # Should not raise — exception is swallowed inside _query_recent_executions
            # We patch at the check_safety_controls level to simulate the 0 return
            pass

        # Verify _query_recent_executions itself swallows exceptions and returns 0
        with patch("boto3.resource") as mock_boto:
            mock_table = MagicMock()
            mock_table.query.side_effect = Exception("connection error")
            mock_boto.return_value.Table.return_value = mock_table
            count = _query_recent_executions(_AUDIT_TABLE, _USER_ARN, hours=1)
        assert count == 0
