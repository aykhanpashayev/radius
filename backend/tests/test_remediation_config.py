"""Unit tests for remediation_engine/config.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.common.errors import ValidationError
from backend.functions.remediation_engine.config import load_config, update_risk_mode

_TABLE = "remediation-config-test"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

class TestLoadConfig:
    def test_returns_defaults_when_table_empty(self):
        with patch("backend.functions.remediation_engine.config.get_item", return_value=None):
            config = load_config(_TABLE)

        assert config["config_id"] == "global"
        assert config["risk_mode"] == "monitor"
        assert config["rules"] == []
        assert config["excluded_arns"] == []
        assert config["protected_account_ids"] == []
        assert config["allowed_ip_ranges"] == []

    def test_returns_stored_values_when_record_exists(self):
        stored = {
            "config_id": "global",
            "risk_mode": "enforce",
            "rules": [{"rule_id": "r1"}],
            "excluded_arns": ["arn:aws:iam::123:user/admin"],
            "protected_account_ids": ["123456789012"],
            "allowed_ip_ranges": ["10.0.0.0/8"],
        }
        with patch("backend.functions.remediation_engine.config.get_item", return_value=stored):
            config = load_config(_TABLE)

        assert config["risk_mode"] == "enforce"
        assert config["rules"] == [{"rule_id": "r1"}]
        assert config["excluded_arns"] == ["arn:aws:iam::123:user/admin"]

    def test_merges_missing_keys_with_defaults(self):
        """Partial record — missing keys should be filled from defaults."""
        partial = {"config_id": "global", "risk_mode": "alert"}
        with patch("backend.functions.remediation_engine.config.get_item", return_value=partial):
            config = load_config(_TABLE)

        assert config["risk_mode"] == "alert"
        assert config["rules"] == []
        assert config["excluded_arns"] == []

    def test_does_not_mutate_default_config(self):
        """Repeated calls with empty table must each return independent dicts."""
        with patch("backend.functions.remediation_engine.config.get_item", return_value=None):
            c1 = load_config(_TABLE)
            c2 = load_config(_TABLE)

        c1["rules"].append({"rule_id": "injected"})
        assert c2["rules"] == []


# ---------------------------------------------------------------------------
# update_risk_mode
# ---------------------------------------------------------------------------

class TestUpdateRiskMode:
    @pytest.mark.parametrize("mode", ["monitor", "alert", "enforce"])
    def test_accepts_valid_modes(self, mode):
        with patch("backend.functions.remediation_engine.config.update_item") as mock_update:
            update_risk_mode(_TABLE, mode)

        mock_update.assert_called_once_with(
            _TABLE,
            key={"config_id": "global"},
            update_expression="SET risk_mode = :mode",
            expression_attribute_values={":mode": mode},
        )

    @pytest.mark.parametrize("bad_mode", ["MONITOR", "Alert", "disabled", "", "block", "passive"])
    def test_raises_validation_error_for_invalid_modes(self, bad_mode):
        with pytest.raises(ValidationError):
            update_risk_mode(_TABLE, bad_mode)

    def test_invalid_mode_does_not_call_dynamodb(self):
        with patch("backend.functions.remediation_engine.config.update_item") as mock_update:
            with pytest.raises(ValidationError):
                update_risk_mode(_TABLE, "invalid")
        mock_update.assert_not_called()
