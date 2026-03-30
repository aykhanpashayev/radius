"""Remediation_Engine Lambda handler.

Reads environment variables, constructs a RemediationRuleEngine, and
processes the incoming incident event.
"""

from __future__ import annotations

import os
from typing import Any

from backend.common.errors import ValidationError
from backend.common.logging_utils import get_logger, put_metric
from backend.functions.remediation_engine.engine import RemediationRuleEngine

logger = get_logger(__name__)

# Read env vars once at cold-start
_CONFIG_TABLE = os.environ["REMEDIATION_CONFIG_TABLE"]
_AUDIT_TABLE = os.environ["REMEDIATION_AUDIT_TABLE"]
_TOPIC_ARN = os.environ["REMEDIATION_TOPIC_ARN"]
_DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# Instantiate engine once for warm-start reuse
_engine = RemediationRuleEngine(
    config_table=_CONFIG_TABLE,
    audit_table=_AUDIT_TABLE,
    topic_arn=_TOPIC_ARN,
    dry_run=_DRY_RUN,
)


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process an incident through the remediation rule engine.

    Args:
        event: Incident dict from Incident_Processor.
        context: Lambda context object.

    Returns:
        {"status": "processed", "result": <RemediationResult dict>}
        or {"status": "skipped", "reason": <str>} on ValidationError.
    """
    incident_id = event.get("incident_id", "unknown")
    logger.info(
        "Remediation_Engine handler invoked",
        extra={"incident_id": incident_id},
    )

    try:
        result = _engine.process(event)
        put_metric("RemediationExecuted", 1, dimensions={
            "Environment": os.environ.get("ENVIRONMENT", "unknown"),
            "Outcome": result.get("outcome", "unknown") if isinstance(result, dict) else "executed",
        })
        return {"status": "processed", "result": result}
    except ValidationError as exc:
        logger.warning(
            "Remediation skipped due to validation error",
            extra={"incident_id": incident_id, "reason": str(exc)},
        )
        return {"status": "skipped", "reason": str(exc)}
