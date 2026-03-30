"""Score_Engine Lambda handler.

Phase 3: real rule-based Blast Radius Score calculation.
Supports single-identity mode (event contains identity_arn) and
batch mode (empty payload — scans all active identities).
"""

import os
import time
from typing import Any

from backend.common.dynamodb_utils import get_dynamodb_client, get_item, put_item
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error, put_metric
from backend.functions.score_engine.context import ScoringContext
from backend.functions.score_engine.engine import RuleEngine
from backend.functions.score_engine.interfaces import ScoreResult

_IDENTITY_PROFILE_TABLE = os.environ["IDENTITY_PROFILE_TABLE"]
_BLAST_RADIUS_SCORE_TABLE = os.environ["BLAST_RADIUS_SCORE_TABLE"]
_EVENT_SUMMARY_TABLE = os.environ["EVENT_SUMMARY_TABLE"]
_TRUST_RELATIONSHIP_TABLE = os.environ["TRUST_RELATIONSHIP_TABLE"]
_INCIDENT_TABLE = os.environ["INCIDENT_TABLE"]

# Instantiated once at module level for Lambda warm-start reuse.
_rule_engine = RuleEngine()


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Calculate blast radius scores for one or all active identities.

    Can be invoked:
    - With a specific identity_arn to score one identity (single mode).
    - With an empty payload to score all active identities (batch mode).

    Args:
        event: Dict optionally containing 'identity_arn'.
        context: Lambda context object.

    Returns:
        Status dict: {"status": "ok", "records_written": N, "failures": M}
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)
    t0 = time.monotonic()

    identity_arn = event.get("identity_arn")
    log.info("Score_Engine invoked", extra={
        "mode": "single" if identity_arn else "batch",
        "identity_arn": identity_arn or "all",
        "correlation_id": correlation_id,
    })

    arns = [identity_arn] if identity_arn else _scan_active_identities()

    tables = {
        "identity_profile": _IDENTITY_PROFILE_TABLE,
        "event_summary": _EVENT_SUMMARY_TABLE,
        "trust_relationship": _TRUST_RELATIONSHIP_TABLE,
        "incident": _INCIDENT_TABLE,
    }

    written, failures = 0, 0
    for arn in arns:
        try:
            ctx = ScoringContext.build(arn, tables)
            if not ctx.identity_profile:
                log.warning("Identity_Profile not found, skipping", extra={"identity_arn": arn})
                continue
            previous = _get_previous_score(arn)
            result = _rule_engine.evaluate(ctx)
            if previous is not None:
                result.previous_score = previous
                result.score_change = result.score_value - previous
            _write_score(result)
            log.info("Score calculated", extra={
                "identity_arn": arn,
                "score_value": result.score_value,
                "severity_level": result.severity_level,
                "contributing_factors": result.contributing_factors,
                "correlation_id": correlation_id,
            })
            written += 1
        except Exception as exc:
            log_error(log, "Failed to score identity", exc, correlation_id, identity_arn=arn)
            failures += 1

    duration_ms = int((time.monotonic() - t0) * 1000)
    log.info("Score_Engine completed", extra={
        "records_written": written,
        "failures": failures,
        "duration_ms": duration_ms,
        "correlation_id": correlation_id,
    })

    env = os.environ.get("ENVIRONMENT", "unknown")
    put_metric("ScoresWritten", written, dimensions={"Environment": env})
    put_metric("ScoringFailures", failures, dimensions={"Environment": env})

    return {"status": "ok", "records_written": written, "failures": failures}


def _get_previous_score(identity_arn: str) -> int | None:
    """Read the current score_value from Blast_Radius_Score table, or None if not found."""
    item = get_item(_BLAST_RADIUS_SCORE_TABLE, {"identity_arn": identity_arn})
    if item and "score_value" in item:
        return int(item["score_value"])
    return None


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
