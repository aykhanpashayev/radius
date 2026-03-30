"""Incident_Processor Lambda handler.

Receives findings from Detection_Engine, creates or deduplicates incidents,
and publishes SNS alerts for high-severity incidents.
"""

import os
import os
from typing import Any

from backend.common.errors import EventProcessingError, ValidationError
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error, put_metric
from backend.functions.incident_processor.processor import (
    append_event_to_incident,
    create_incident,
    find_duplicate,
    publish_alert,
    validate_finding,
)

logger = get_logger(__name__)

_INCIDENT_TABLE = os.environ["INCIDENT_TABLE"]
_SNS_TOPIC_ARN = os.environ["SNS_TOPIC_ARN"]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process a finding and create or update an incident.

    Args:
        event: Finding dict from Detection_Engine.
        context: Lambda context object.

    Returns:
        Status dict with incident_id.
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)

    log.info("Incident_Processor received finding", extra={
        "identity_arn": event.get("identity_arn"),
        "detection_type": event.get("detection_type"),
        "severity": event.get("severity"),
        "correlation_id": correlation_id,
    })

    try:
        validate_finding(event)
    except ValidationError as exc:
        log_error(log, "Invalid finding — skipping", exc, correlation_id)
        return {"status": "skipped", "reason": str(exc)}

    identity_arn = event["identity_arn"]
    detection_type = event["detection_type"]
    new_event_ids = event.get("related_event_ids", [])

    try:
        # Check for duplicate within last 24 hours
        duplicate = find_duplicate(_INCIDENT_TABLE, identity_arn, detection_type)

        if duplicate:
            incident_id = duplicate["incident_id"]
            log.info("Duplicate incident found — appending events", extra={
                "incident_id": incident_id,
                "correlation_id": correlation_id,
            })
            append_event_to_incident(_INCIDENT_TABLE, incident_id, new_event_ids)
            return {"status": "deduplicated", "incident_id": incident_id}

        # Create new incident
        incident = create_incident(_INCIDENT_TABLE, event)
        put_metric("IncidentsCreated", 1, dimensions={
            "Environment": os.environ.get("ENVIRONMENT", "unknown"),
            "Severity": incident.get("severity", "unknown"),
        })

        # Alert for high-severity incidents
        try:
            publish_alert(_SNS_TOPIC_ARN, incident)
        except Exception as exc:
            log_error(log, "SNS alert failed (non-fatal)", exc, correlation_id,
                      incident_id=incident["incident_id"])

        return {"status": "created", "incident_id": incident["incident_id"]}

    except Exception as exc:
        log_error(log, "Incident_Processor failed", exc, correlation_id,
                  identity_arn=identity_arn)
        raise EventProcessingError(str(exc)) from exc
