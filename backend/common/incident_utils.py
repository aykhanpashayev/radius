"""Shared incident status transition logic.

Extracted from incident_processor/processor.py so that api_handler
can perform status transitions without importing from another Lambda's
package directory.
"""

from typing import Any

from backend.common.dynamodb_utils import update_item
from backend.common.errors import ValidationError
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

_VALID_STATUSES = {"open", "investigating", "resolved", "false_positive"}
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"investigating", "false_positive"},
    "investigating": {"resolved", "false_positive"},
    "resolved": set(),
    "false_positive": set(),
}


def transition_status(
    table_name: str,
    incident_id: str,
    current_status: str,
    new_status: str,
) -> dict[str, Any]:
    """Transition an incident to a new status and append to its history.

    Args:
        table_name: Incident DynamoDB table name.
        incident_id: Incident ID.
        current_status: Current status (for transition validation).
        new_status: Target status.

    Returns:
        Updated incident attributes from DynamoDB.

    Raises:
        ValidationError: If the transition is not permitted.
    """
    if new_status not in _VALID_STATUSES:
        raise ValidationError(f"Invalid status: {new_status!r}")

    allowed = _VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValidationError(
            f"Invalid transition {current_status!r} → {new_status!r}. "
            f"Allowed: {sorted(allowed)}"
        )

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec="microseconds")

    return update_item(
        table_name=table_name,
        key={"incident_id": incident_id},
        update_expression=(
            "SET #st = :new_status, "
            "update_timestamp = :now, "
            "status_history = list_append(if_not_exists(status_history, :empty), :entry)"
        ),
        expression_attribute_values={
            ":new_status": new_status,
            ":now": now,
            ":entry": [{"status": new_status, "timestamp": now}],
            ":empty": [],
        },
        expression_attribute_names={"#st": "status"},
    )
