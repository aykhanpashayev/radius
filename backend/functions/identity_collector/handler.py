"""Identity_Collector Lambda handler.

Invoked asynchronously by Event_Normalizer.
Updates Identity_Profile and records Trust_Relationship edges.
"""

import os
from typing import Any

from backend.common.errors import EventProcessingError
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error
from backend.functions.identity_collector.collector import (
    _ASSUME_ROLE_EVENTS,
    _DELETION_EVENTS,
    mark_identity_inactive,
    record_trust_relationship,
    upsert_identity_profile,
)

logger = get_logger(__name__)

_IDENTITY_PROFILE_TABLE = os.environ["IDENTITY_PROFILE_TABLE"]
_TRUST_RELATIONSHIP_TABLE = os.environ["TRUST_RELATIONSHIP_TABLE"]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process an event to update identity and trust data.

    Args:
        event: Dict with keys 'event_summary' and 'raw_event'.
        context: Lambda context object.

    Returns:
        Status dict.
    """
    correlation_id = generate_correlation_id()
    log = get_logger(__name__, correlation_id)

    event_summary = event.get("event_summary", event)
    raw_event = event.get("raw_event", {})

    identity_arn = event_summary.get("identity_arn", "")
    event_type = event_summary.get("event_type", "")
    event_id = event_summary.get("event_id", "unknown")

    if not identity_arn:
        log.warning("Identity_Collector received event with no identity_arn",
                    extra={"event_id": event_id})
        return {"status": "skipped", "reason": "no identity_arn"}

    log.info("Processing identity event", extra={
        "identity_arn": identity_arn,
        "event_type": event_type,
        "event_id": event_id,
    })

    try:
        # Always upsert the identity profile
        upsert_identity_profile(_IDENTITY_PROFILE_TABLE, identity_arn, event_summary)

        # Record trust relationship for AssumeRole events
        if event_type in _ASSUME_ROLE_EVENTS:
            record_trust_relationship(
                _TRUST_RELATIONSHIP_TABLE, event_summary, raw_event
            )

        # Mark identity inactive on deletion events
        if event_type in _DELETION_EVENTS:
            mark_identity_inactive(_IDENTITY_PROFILE_TABLE, identity_arn)

    except Exception as exc:
        log_error(log, "Identity_Collector processing failed", exc, correlation_id,
                  identity_arn=identity_arn, event_id=event_id)
        raise EventProcessingError(str(exc)) from exc

    return {"status": "ok", "identity_arn": identity_arn, "event_id": event_id}
