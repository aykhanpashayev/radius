"""Detection_Engine Lambda handler — PLACEHOLDER.

Phase 2: logs received events and forwards a placeholder finding to
Incident_Processor to keep the pipeline testable end-to-end.
No real detection logic is implemented here.
"""

import json
import os
from typing import Any

import boto3

from backend.common.logging_utils import generate_correlation_id, get_logger, log_error

logger = get_logger(__name__)

_INCIDENT_PROCESSOR_ARN = os.environ["INCIDENT_PROCESSOR_ARN"]
_lambda_client = boto3.client("lambda")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Receive an Event_Summary and forward a placeholder finding.

    Args:
        event: Event_Summary dict passed from Event_Normalizer.
        context: Lambda context object.

    Returns:
        Status dict.
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)

    event_id = event.get("event_id", "unknown")
    identity_arn = event.get("identity_arn", "unknown")
    event_type = event.get("event_type", "unknown")

    log.info(
        "Detection_Engine received event (PLACEHOLDER — no detection logic)",
        extra={
            "event_id": event_id,
            "identity_arn": identity_arn,
            "event_type": event_type,
            "correlation_id": correlation_id,
        },
    )

    # --- Placeholder: forward a test finding to Incident_Processor ---
    # This exists solely to keep the pipeline testable in Phase 2.
    # Real detection rules will replace this in a future phase.
    placeholder_finding = {
        "identity_arn": identity_arn,
        "detection_type": "PLACEHOLDER_DETECTION",
        "severity": "Low",
        "confidence": 0,
        "related_event_ids": [event_id],
        "description": "Placeholder finding — Detection_Engine not yet implemented",
        "correlation_id": correlation_id,
    }

    try:
        _lambda_client.invoke(
            FunctionName=_INCIDENT_PROCESSOR_ARN,
            InvocationType="Event",
            Payload=json.dumps(placeholder_finding, default=str),
        )
        log.info("Forwarded placeholder finding to Incident_Processor",
                 extra={"correlation_id": correlation_id})
    except Exception as exc:
        log_error(log, "Failed to invoke Incident_Processor", exc, correlation_id)

    return {"status": "ok", "event_id": event_id, "placeholder": True}
