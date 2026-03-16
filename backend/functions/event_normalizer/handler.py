"""Event_Normalizer Lambda handler.

Triggered by EventBridge with CloudTrail management events.
Parses and stores Event_Summary, then asynchronously invokes
Detection_Engine and Identity_Collector.
"""

import json
import os
from typing import Any

import boto3

from backend.common.errors import EventProcessingError, ValidationError
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error
from backend.common.dynamodb_utils import put_item
from backend.functions.event_normalizer.normalizer import parse_cloudtrail_event

logger = get_logger(__name__)

_EVENT_SUMMARY_TABLE = os.environ["EVENT_SUMMARY_TABLE"]
_DETECTION_ENGINE_ARN = os.environ["DETECTION_ENGINE_ARN"]
_IDENTITY_COLLECTOR_ARN = os.environ["IDENTITY_COLLECTOR_ARN"]
_SCORE_ENGINE_FUNCTION_NAME = os.environ.get("SCORE_ENGINE_FUNCTION_NAME", "")

_lambda_client = boto3.client("lambda")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process a CloudTrail event from EventBridge.

    Args:
        event: EventBridge event containing CloudTrail detail.
        context: Lambda context object.

    Returns:
        Status dict with processed event ID.
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)

    event_id = event.get("detail", {}).get("eventID", "unknown")
    log.info("Processing CloudTrail event", extra={"event_id": event_id})

    try:
        event_summary = parse_cloudtrail_event(event)
    except ValidationError as exc:
        log_error(log, "Skipping invalid CloudTrail event", exc, correlation_id,
                  event_id=event_id)
        return {"status": "skipped", "reason": str(exc), "event_id": event_id}

    # Store in Event_Summary table
    try:
        put_item(_EVENT_SUMMARY_TABLE, event_summary)
        log.info("Stored Event_Summary", extra={
            "event_id": event_summary["event_id"],
            "identity_arn": event_summary["identity_arn"],
            "event_type": event_summary["event_type"],
        })
    except Exception as exc:
        log_error(log, "Failed to store Event_Summary", exc, correlation_id,
                  event_id=event_id)
        raise EventProcessingError(f"DynamoDB write failed: {exc}") from exc

    # Invoke Detection_Engine asynchronously
    _invoke_async(
        log, _DETECTION_ENGINE_ARN, event_summary,
        correlation_id=correlation_id, target="Detection_Engine",
    )

    # Invoke Identity_Collector asynchronously
    _invoke_async(
        log, _IDENTITY_COLLECTOR_ARN,
        {"event_summary": event_summary, "raw_event": event.get("detail", event)},
        correlation_id=correlation_id, target="Identity_Collector",
    )

    # Invoke Score_Engine asynchronously to rescore this identity
    if _SCORE_ENGINE_FUNCTION_NAME:
        _invoke_async(
            log, _SCORE_ENGINE_FUNCTION_NAME,
            {"identity_arn": event_summary["identity_arn"]},
            correlation_id=correlation_id, target="Score_Engine",
        )

    return {"status": "ok", "event_id": event_summary["event_id"]}


def _invoke_async(
    log,
    function_arn: str,
    payload: dict[str, Any],
    correlation_id: str,
    target: str,
) -> None:
    """Invoke a Lambda function asynchronously (Event invocation type).

    Logs failures but does not raise — the caller should not fail because
    a downstream async invocation failed.
    """
    try:
        _lambda_client.invoke(
            FunctionName=function_arn,
            InvocationType="Event",
            Payload=json.dumps(payload, default=str),
        )
        log.info(f"Invoked {target} asynchronously",
                 extra={"target": target, "correlation_id": correlation_id})
    except Exception as exc:
        log_error(log, f"Failed to invoke {target}", exc, correlation_id,
                  target=target)
