"""Remediation_Engine configuration management.

Loads the singleton config record from Remediation_Config table and
provides a helper to update the global Risk_Mode.
"""

import copy
from typing import Any

from backend.common.dynamodb_utils import get_item, update_item
from backend.common.errors import ValidationError

_VALID_MODES = {"monitor", "alert", "enforce"}
_CONFIG_ID = "global"

_DEFAULT_CONFIG: dict[str, Any] = {
    "config_id": _CONFIG_ID,
    "risk_mode": "monitor",
    "rules": [],
    "excluded_arns": [],
    "protected_account_ids": [],
    "allowed_ip_ranges": [],
}


def load_config(config_table: str) -> dict[str, Any]:
    """Load the global remediation config from DynamoDB.

    Returns safe defaults (monitor mode, empty rules) when the record
    does not exist yet (first deployment).

    Args:
        config_table: Name of the Remediation_Config DynamoDB table.

    Returns:
        Config dict with keys: config_id, risk_mode, rules,
        excluded_arns, protected_account_ids, allowed_ip_ranges.
    """
    item = get_item(config_table, {"config_id": _CONFIG_ID})
    if item is None:
        return copy.deepcopy(_DEFAULT_CONFIG)

    # Merge with defaults so any missing keys are always present
    merged = copy.deepcopy(_DEFAULT_CONFIG)
    merged.update(item)
    return merged


def update_risk_mode(config_table: str, new_mode: str) -> None:
    """Update the global Risk_Mode in the Remediation_Config table.

    Args:
        config_table: Name of the Remediation_Config DynamoDB table.
        new_mode: New risk mode — must be one of 'monitor', 'alert', 'enforce'.

    Raises:
        ValidationError: If new_mode is not a valid risk mode.
    """
    if new_mode not in _VALID_MODES:
        raise ValidationError(
            f"Invalid risk_mode: {new_mode!r}. Must be one of {sorted(_VALID_MODES)}."
        )
    update_item(
        config_table,
        key={"config_id": _CONFIG_ID},
        update_expression="SET risk_mode = :mode",
        expression_attribute_values={":mode": new_mode},
    )
