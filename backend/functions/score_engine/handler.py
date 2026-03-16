"""Score_Engine Lambda handler — PLACEHOLDER.

Phase 2: logs invocations and writes placeholder Blast_Radius_Score records
(score=50, severity=Moderate) to keep the data pipeline and API endpoints
testable. No real scoring algorithms are implemented here.
"""

import os
from datetime import datetime, timezone
from typing import Any

from backend.common.dynamodb_utils import put_item, get_dynamodb_client
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error
from backend.functions.score_engine.interfaces import ScoreResult, classify_severity

logger = get_logger(__name__)

_IDENTITY_PROFILE_TABLE = os.environ["IDENTITY_PROFILE_TABLE"]
_BLAST_RADIUS_SCORE_TABLE = os.environ["BLAST_RADIUS_SCORE_TABLE"]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Calculate (placeholder) blast radius scores.

    Can be invoked:
    - With a specific identity_arn to score one identity.
    - With an empty payload to score all active identities (scan).

    Args:
        event: Dict optionally containing 'identity_arn'.
        context: Lambda context object.

    Returns:
        Status dict with count of records written.
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)

    identity_arn = event.get("identity_arn")

    log.info(
        "Score_Engine invoked (PLACEHOLDER — no scoring logic)",
        extra={
            "identity_arn": identity_arn or "all",
            "correlation_id": correlation_id,
        },
    )

    if identity_arn:
        arns = [identity_arn]
    else:
        arns = _scan_active_identities()

    written = 0
    for arn in arns:
        try:
            result = ScoreResult.placeholder(arn)
            _write_score(result)
            written += 1
        except Exception as exc:
            log_error(log, "Failed to write placeholder score", exc, correlation_id,
                      identity_arn=arn)

    log.info("Score_Engine completed", extra={
        "records_written": written,
        "correlation_id": correlation_id,
    })
    return {"status": "ok", "records_written": written, "placeholder": True}


def _write_score(result: ScoreResult) -> None:
    """Write a ScoreResult to the Blast_Radius_Score table."""
    item: dict[str, Any] = {
        "identity_arn": result.identity_arn,
        "score_value": result.score_value,
        "severity_level": result.severity_level,
        "calculation_timestamp": result.calculation_timestamp,
        "contributing_factors": result.contributing_factors,
    }
    if result.previous_score is not None:
        item["previous_score"] = result.previous_score
    if result.score_change is not None:
        item["score_change"] = result.score_change

    put_item(_BLAST_RADIUS_SCORE_TABLE, item)


def _scan_active_identities() -> list[str]:
    """Scan Identity_Profile table for active identity ARNs.

    Returns:
        List of identity ARN strings.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(_IDENTITY_PROFILE_TABLE)

    arns: list[str] = []
    kwargs: dict[str, Any] = {
        "ProjectionExpression": "identity_arn",
        "FilterExpression": "is_active = :active",
        "ExpressionAttributeValues": {":active": True},
    }

    while True:
        response = table.scan(**kwargs)
        arns.extend(item["identity_arn"] for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key

    return arns
