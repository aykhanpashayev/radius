"""Remediation_Engine configuration management.

Delegates to backend.common.remediation_config — the shared module that
both this function and api_handler use. Kept here for backwards
compatibility with internal imports within this Lambda package.
"""

from backend.common.remediation_config import (  # noqa: F401
    _DEFAULT_CONFIG,
    _CONFIG_ID,
    _VALID_MODES,
    load_config,
    update_risk_mode,
)
