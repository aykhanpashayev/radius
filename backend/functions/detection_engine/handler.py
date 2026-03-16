"""Detection_Engine Lambda handler.

Phase 4: real rule-based detection logic replacing the Phase 2 placeholder.
Evaluates all 7 detection rules against each incoming Event_Summary and
forwards any triggered Findings to Incident_Processor.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any

import boto3

from backend.common.logging_utils import generate_correlation_id, get_logger, log_error
from backend.functions.detection_engine.context import DetectionContext
from backend.functions.detection_engine.engine import RuleEngine

logger = get_logger(__name__)

_INCIDENT_PROCESSOR_ARN = os.environ["INCIDENT_PROCESSOR_ARN"]
_EVENT_SUMMARY_TABLE = os.environ["EVENT_SUMMARY_TABLE"]

# Instantiated once at module level for Lambda warm-start reuse
_engine = RuleEngine()
_lambda_client = boto3.client("lambda")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Evaluate detection rules against an Event_Summary and forward findings.

    Args:
        event: Event_Summary dict passed from Event_Normalizer.
        context: Lambda context object.

    Returns:
        {"status": "ok", "findings": N, "failures": M}
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)

    identity_arn = event.get("identity_arn", "unknown")
    event_id = event.get("event_id", "unknown")
    event_timestamp = event.get("timestamp", "")

    log.info(
        "Detection_Engine received event",
        extra={
            "event_id": event_id,
            "identity_arn": identity_arn,
            "correlation_id": correlation_id,
        },
    )

    # Build detection context (two DynamoDB queries)
    det_context = DetectionContext.build(
        identity_arn=identity_arn,
        current_event_id=event_id,
        current_event_timestamp=event_timestamp,
        event_summary_table=_EVENT_SUMMARY_TABLE,
    )

    # Evaluate all rules
    findings = _engine.evaluate(event, det_context)

    log.info(
        "Detection_Engine evaluation complete",
        extra={
            "event_id": event_id,
            "findings_count": len(findings),
            "correlation_id": correlation_id,
        },
    )

    # Forward each finding to Incident_Processor
    forwarded = 0
    failures = 0

    for finding in findings:
        payload = asdict(finding)
        payload["correlation_id"] = correlation_id

        try:
            _lambda_client.invoke(
                FunctionName=_INCIDENT_PROCESSOR_ARN,
                InvocationType="Event",
                Payload=json.dumps(payload, default=str),
            )
            forwarded += 1
            log.info(
                "Forwarded finding to Incident_Processor",
                extra={
                    "detection_type": finding.detection_type,
                    "severity": finding.severity,
                    "correlation_id": correlation_id,
                },
            )
        except Exception as exc:
            failures += 1
            log_error(log, "Failed to invoke Incident_Processor", exc, correlation_id)

    return {"status": "ok", "findings": forwarded, "failures": failures}
