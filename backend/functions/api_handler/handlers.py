"""Endpoint handler functions for API_Handler Lambda.

Each function receives (path_params, query_params, raw_event) and returns
an API Gateway proxy response dict via the utils helpers.

Supported operations:
  GET  /identities
  GET  /identities/{arn}
  GET  /scores
  GET  /scores/{arn}
  GET  /incidents
  GET  /incidents/{id}
  PATCH /incidents/{id}
  GET  /events
  GET  /events/{id}
  GET  /trust-relationships
  GET  /remediation/config
  PUT  /remediation/config/mode
  GET  /remediation/rules
  POST /remediation/rules
  DELETE /remediation/rules/{rule_id}
  GET  /remediation/audit
"""

import json
import os
import time
import uuid
from typing import Any
from urllib.parse import unquote

import boto3
from boto3.dynamodb.conditions import Key

from backend.common.dynamodb_utils import get_dynamodb_client, get_item, query_gsi
from backend.common.errors import DynamoDBError, ValidationError
from backend.common.logging_utils import get_logger
from backend.functions.api_handler.utils import (
    bad_request,
    not_found,
    ok,
    parse_exclusive_start_key,
    parse_limit,
    server_error,
)

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Table names from environment
# ---------------------------------------------------------------------------
_IDENTITY_TABLE = os.environ.get("IDENTITY_PROFILE_TABLE", "")
_SCORE_TABLE = os.environ.get("BLAST_RADIUS_SCORE_TABLE", "")
_INCIDENT_TABLE = os.environ.get("INCIDENT_TABLE", "")
_EVENT_TABLE = os.environ.get("EVENT_SUMMARY_TABLE", "")
_TRUST_TABLE = os.environ.get("TRUST_RELATIONSHIP_TABLE", "")
_REMEDIATION_CONFIG_TABLE = os.environ.get("REMEDIATION_CONFIG_TABLE", "")
_REMEDIATION_AUDIT_TABLE = os.environ.get("REMEDIATION_AUDIT_TABLE", "")

_VALID_RISK_MODES = {"monitor", "alert", "enforce"}
_VALID_SEVERITIES = {"Low", "Moderate", "High", "Very High", "Critical"}
_REMEDIATION_CONFIG_ID = "global"

# Valid incident statuses and allowed transitions (mirrors processor.py)
_VALID_STATUSES = {"open", "investigating", "resolved", "false_positive"}
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "open": {"investigating", "false_positive"},
    "investigating": {"resolved", "false_positive"},
    "resolved": set(),
    "false_positive": set(),
}


# ===========================================================================
# /identities
# ===========================================================================

def list_identities(
    path_params: dict[str, str],
    query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /identities — list identity profiles with optional filters."""
    try:
        limit = parse_limit(query_params)
        start_key = parse_exclusive_start_key(query_params)
    except ValidationError as exc:
        return bad_request(str(exc))

    identity_type = query_params.get("identity_type")
    account_id = query_params.get("account_id")

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_IDENTITY_TABLE)

        if identity_type:
            # IdentityTypeIndex: PK=identity_type, SK=account_id
            kwargs: dict[str, Any] = {
                "IndexName": "IdentityTypeIndex",
                "KeyConditionExpression": Key("identity_type").eq(identity_type),
                "Limit": limit,
            }
            if account_id:
                kwargs["KeyConditionExpression"] &= Key("account_id").eq(account_id)
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif account_id:
            # AccountIndex: PK=account_id, SK=last_activity_timestamp
            kwargs = {
                "IndexName": "AccountIndex",
                "KeyConditionExpression": Key("account_id").eq(account_id),
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        else:
            # Full scan (no filter) — acceptable for Phase 2 scale
            kwargs = {"Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)

    except DynamoDBError as exc:
        logger.error("DynamoDB error in list_identities", extra={"error": str(exc)})
        return server_error(str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return ok(resp.get("Items", []), resp.get("LastEvaluatedKey"), elapsed)


def get_identity(
    path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /identities/{arn} — retrieve a single identity profile."""
    arn = unquote(path_params.get("arn", ""))
    if not arn:
        return bad_request("Missing path parameter: arn")

    try:
        item = get_item(_IDENTITY_TABLE, {"identity_arn": arn})
    except DynamoDBError as exc:
        return server_error(str(exc))

    if item is None:
        return not_found(f"Identity {arn!r}")
    return ok(item)


# ===========================================================================
# /scores
# ===========================================================================

def list_scores(
    path_params: dict[str, str],
    query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /scores — list blast radius scores with optional severity/range filters."""
    try:
        limit = parse_limit(query_params)
        start_key = parse_exclusive_start_key(query_params)
    except ValidationError as exc:
        return bad_request(str(exc))

    severity_level = query_params.get("severity_level")
    min_score = query_params.get("min_score")
    max_score = query_params.get("max_score")

    # Validate numeric score params
    if min_score is not None:
        try:
            min_score_val = float(min_score)
        except ValueError:
            return bad_request("'min_score' must be a number")
    else:
        min_score_val = None

    if max_score is not None:
        try:
            max_score_val = float(max_score)
        except ValueError:
            return bad_request("'max_score' must be a number")
    else:
        max_score_val = None

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_SCORE_TABLE)

        if severity_level:
            # SeverityIndex: PK=severity_level, SK=calculation_timestamp
            kwargs: dict[str, Any] = {
                "IndexName": "SeverityIndex",
                "KeyConditionExpression": Key("severity_level").eq(severity_level),
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif min_score_val is not None or max_score_val is not None:
            # ScoreRangeIndex: PK=severity_level — can't range-query without PK.
            # Fall back to scan with filter for score range.
            from boto3.dynamodb.conditions import Attr
            filter_parts = []
            if min_score_val is not None:
                filter_parts.append(Attr("score_value").gte(min_score_val))
            if max_score_val is not None:
                filter_parts.append(Attr("score_value").lte(max_score_val))
            filter_expr = filter_parts[0]
            for part in filter_parts[1:]:
                filter_expr = filter_expr & part

            kwargs = {"FilterExpression": filter_expr, "Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)

        else:
            kwargs = {"Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)

    except DynamoDBError as exc:
        return server_error(str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return ok(resp.get("Items", []), resp.get("LastEvaluatedKey"), elapsed)


def get_score(
    path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /scores/{arn} — retrieve blast radius score for a specific identity."""
    arn = unquote(path_params.get("arn", ""))
    if not arn:
        return bad_request("Missing path parameter: arn")

    try:
        item = get_item(_SCORE_TABLE, {"identity_arn": arn})
    except DynamoDBError as exc:
        return server_error(str(exc))

    if item is None:
        return not_found(f"Score for identity {arn!r}")
    return ok(item)


# ===========================================================================
# /incidents
# ===========================================================================

def list_incidents(
    path_params: dict[str, str],
    query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /incidents — list incidents with optional status/severity/identity filters."""
    try:
        limit = parse_limit(query_params)
        start_key = parse_exclusive_start_key(query_params)
    except ValidationError as exc:
        return bad_request(str(exc))

    status = query_params.get("status")
    severity = query_params.get("severity")
    identity_arn = query_params.get("identity_arn")
    start_date = query_params.get("start_date")
    end_date = query_params.get("end_date")

    # Unsupported combination: identity_arn + status has no composite GSI
    if identity_arn and status:
        return bad_request(
            "Filtering by both 'identity_arn' and 'status' is not supported. "
            "Use one filter at a time."
        )

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_INCIDENT_TABLE)

        if status:
            # StatusIndex: PK=status, SK=creation_timestamp
            key_cond = Key("status").eq(status)
            if start_date:
                key_cond = key_cond & Key("creation_timestamp").gte(start_date)
            kwargs: dict[str, Any] = {
                "IndexName": "StatusIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif severity:
            # SeverityIndex: PK=severity, SK=creation_timestamp
            key_cond = Key("severity").eq(severity)
            if start_date:
                key_cond = key_cond & Key("creation_timestamp").gte(start_date)
            kwargs = {
                "IndexName": "SeverityIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif identity_arn:
            # IdentityIndex: PK=identity_arn, SK=creation_timestamp
            key_cond = Key("identity_arn").eq(identity_arn)
            if start_date:
                key_cond = key_cond & Key("creation_timestamp").gte(start_date)
            kwargs = {
                "IndexName": "IdentityIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        else:
            from boto3.dynamodb.conditions import Attr
            scan_kwargs: dict[str, Any] = {"Limit": limit}
            if start_date or end_date:
                filters = []
                if start_date:
                    filters.append(Attr("creation_timestamp").gte(start_date))
                if end_date:
                    filters.append(Attr("creation_timestamp").lte(end_date))
                scan_kwargs["FilterExpression"] = filters[0] if len(filters) == 1 else filters[0] & filters[1]
            if start_key:
                scan_kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**scan_kwargs)

    except DynamoDBError as exc:
        return server_error(str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return ok(resp.get("Items", []), resp.get("LastEvaluatedKey"), elapsed)


def get_incident(
    path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /incidents/{id} — retrieve a single incident by ID."""
    incident_id = path_params.get("id", "")
    if not incident_id:
        return bad_request("Missing path parameter: id")

    try:
        item = get_item(_INCIDENT_TABLE, {"incident_id": incident_id})
    except DynamoDBError as exc:
        return server_error(str(exc))

    if item is None:
        return not_found(f"Incident {incident_id!r}")
    return ok(item)


def patch_incident(
    path_params: dict[str, str],
    _query_params: dict[str, str],
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    """PATCH /incidents/{id} — update incident status."""
    incident_id = path_params.get("id", "")
    if not incident_id:
        return bad_request("Missing path parameter: id")

    # Parse body
    try:
        body = json.loads(raw_event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Request body must be valid JSON")

    new_status = body.get("status")
    if not new_status:
        return bad_request("Request body must include 'status'")
    if new_status not in _VALID_STATUSES:
        return bad_request(
            f"Invalid status {new_status!r}. Must be one of: {sorted(_VALID_STATUSES)}"
        )

    # Fetch current incident
    try:
        incident = get_item(_INCIDENT_TABLE, {"incident_id": incident_id})
    except DynamoDBError as exc:
        return server_error(str(exc))

    if incident is None:
        return not_found(f"Incident {incident_id!r}")

    current_status = incident.get("status", "")
    allowed = _VALID_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        return bad_request(
            f"Cannot transition from {current_status!r} to {new_status!r}. "
            f"Allowed transitions: {sorted(allowed) or 'none'}"
        )

    # Apply the transition via processor helper
    from backend.functions.incident_processor.processor import transition_status
    try:
        updated = transition_status(_INCIDENT_TABLE, incident_id, current_status, new_status)
    except DynamoDBError as exc:
        return server_error(str(exc))

    return ok(updated)


# ===========================================================================
# /events
# ===========================================================================

def list_events(
    path_params: dict[str, str],
    query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /events — list event summaries with optional filters."""
    try:
        limit = parse_limit(query_params)
        start_key = parse_exclusive_start_key(query_params)
    except ValidationError as exc:
        return bad_request(str(exc))

    identity_arn = query_params.get("identity_arn")
    event_type = query_params.get("event_type")
    start_date = query_params.get("start_date")
    end_date = query_params.get("end_date")

    # Unsupported: identity_arn + event_type has no composite GSI
    if identity_arn and event_type:
        return bad_request(
            "Filtering by both 'identity_arn' and 'event_type' is not supported. "
            "Use one filter at a time."
        )

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_EVENT_TABLE)

        if identity_arn:
            # Primary table: PK=identity_arn, SK=timestamp
            key_cond = Key("identity_arn").eq(identity_arn)
            if start_date:
                key_cond = key_cond & Key("timestamp").gte(start_date)
            kwargs: dict[str, Any] = {
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if end_date:
                from boto3.dynamodb.conditions import Attr
                kwargs["FilterExpression"] = Attr("timestamp").lte(end_date)
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif event_type:
            # EventTypeIndex: PK=event_type, SK=timestamp
            key_cond = Key("event_type").eq(event_type)
            if start_date:
                key_cond = key_cond & Key("timestamp").gte(start_date)
            kwargs = {
                "IndexName": "EventTypeIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif start_date:
            # TimeRangeIndex: PK=date_partition, SK=timestamp
            # date_partition is YYYY-MM-DD derived from start_date
            date_partition = start_date[:10]
            key_cond = Key("date_partition").eq(date_partition)
            if start_date:
                key_cond = key_cond & Key("timestamp").gte(start_date)
            kwargs = {
                "IndexName": "TimeRangeIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        else:
            kwargs = {"Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)

    except DynamoDBError as exc:
        return server_error(str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return ok(resp.get("Items", []), resp.get("LastEvaluatedKey"), elapsed)


def get_event(
    path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /events/{id} — retrieve a single event summary by event_id."""
    event_id = path_params.get("id", "")
    if not event_id:
        return bad_request("Missing path parameter: id")

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_EVENT_TABLE)
        # EventIdIndex: PK=event_id (ALL projection)
        resp = table.query(
            IndexName="EventIdIndex",
            KeyConditionExpression=Key("event_id").eq(event_id),
            Limit=1,
        )
    except DynamoDBError as exc:
        return server_error(str(exc))

    items = resp.get("Items", [])
    if not items:
        return not_found(f"Event {event_id!r}")
    return ok(items[0])


# ===========================================================================
# /trust-relationships
# ===========================================================================

def list_trust_relationships(
    path_params: dict[str, str],
    query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /trust-relationships — list trust relationships with optional filters."""
    try:
        limit = parse_limit(query_params)
        start_key = parse_exclusive_start_key(query_params)
    except ValidationError as exc:
        return bad_request(str(exc))

    source_arn = query_params.get("source_arn")
    target_account_id = query_params.get("target_account_id")
    relationship_type = query_params.get("relationship_type")

    # Unsupported: source_arn + relationship_type has no composite GSI
    if source_arn and relationship_type:
        return bad_request(
            "Filtering by both 'source_arn' and 'relationship_type' is not supported. "
            "Use one filter at a time."
        )

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_TRUST_TABLE)

        if source_arn:
            # Primary table: PK=source_arn, SK=target_arn
            kwargs: dict[str, Any] = {
                "KeyConditionExpression": Key("source_arn").eq(source_arn),
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif relationship_type:
            # RelationshipTypeIndex: PK=relationship_type, SK=discovery_timestamp
            kwargs = {
                "IndexName": "RelationshipTypeIndex",
                "KeyConditionExpression": Key("relationship_type").eq(relationship_type),
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif target_account_id:
            # TargetAccountIndex: PK=target_account_id, SK=discovery_timestamp
            kwargs = {
                "IndexName": "TargetAccountIndex",
                "KeyConditionExpression": Key("target_account_id").eq(target_account_id),
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        else:
            kwargs = {"Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)

    except DynamoDBError as exc:
        return server_error(str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return ok(resp.get("Items", []), resp.get("LastEvaluatedKey"), elapsed)


# ===========================================================================
# /remediation/config
# ===========================================================================

def get_remediation_config(
    _path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /remediation/config — return the global remediation configuration."""
    from backend.functions.remediation_engine.config import load_config
    try:
        config = load_config(_REMEDIATION_CONFIG_TABLE)
    except DynamoDBError as exc:
        return server_error(str(exc))
    return ok(config)


def put_remediation_mode(
    _path_params: dict[str, str],
    _query_params: dict[str, str],
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    """PUT /remediation/config/mode — update the global risk mode."""
    try:
        body = json.loads(raw_event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Request body must be valid JSON")

    new_mode = body.get("risk_mode")
    if not new_mode:
        return bad_request("Request body must include 'risk_mode'")
    if new_mode not in _VALID_RISK_MODES:
        return bad_request(
            f"Invalid risk_mode {new_mode!r}. Must be one of: {sorted(_VALID_RISK_MODES)}"
        )

    from backend.functions.remediation_engine.config import update_risk_mode
    try:
        update_risk_mode(_REMEDIATION_CONFIG_TABLE, new_mode)
    except ValidationError as exc:
        return bad_request(str(exc))
    except DynamoDBError as exc:
        return server_error(str(exc))

    return ok({"risk_mode": new_mode, "updated": True})


# ===========================================================================
# /remediation/rules
# ===========================================================================

def list_remediation_rules(
    _path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /remediation/rules — return the rules list from the global config."""
    from backend.functions.remediation_engine.config import load_config
    try:
        config = load_config(_REMEDIATION_CONFIG_TABLE)
    except DynamoDBError as exc:
        return server_error(str(exc))
    return ok(config.get("rules", []))


def create_remediation_rule(
    _path_params: dict[str, str],
    _query_params: dict[str, str],
    raw_event: dict[str, Any],
) -> dict[str, Any]:
    """POST /remediation/rules — append a new rule to the global config."""
    try:
        body = json.loads(raw_event.get("body") or "{}")
    except json.JSONDecodeError:
        return bad_request("Request body must be valid JSON")

    # Validate required fields
    name = body.get("name", "").strip()
    if not name:
        return bad_request("Rule must include a non-empty 'name'")

    min_severity = body.get("min_severity", "Low")
    if min_severity not in _VALID_SEVERITIES:
        return bad_request(
            f"Invalid min_severity {min_severity!r}. Must be one of: {sorted(_VALID_SEVERITIES)}"
        )

    actions = body.get("actions", [])
    if not isinstance(actions, list) or not actions:
        return bad_request("Rule must include a non-empty 'actions' list")

    rule = {
        "rule_id": str(uuid.uuid4()),
        "name": name,
        "active": bool(body.get("active", True)),
        "min_severity": min_severity,
        "detection_types": body.get("detection_types") or [],
        "identity_types": body.get("identity_types") or [],
        "actions": actions,
        "priority": int(body.get("priority", 100)),
    }

    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_REMEDIATION_CONFIG_TABLE)
        # Append to the rules list; initialise record if absent
        table.update_item(
            Key={"config_id": _REMEDIATION_CONFIG_ID},
            UpdateExpression=(
                "SET #r = list_append(if_not_exists(#r, :empty), :new_rule)"
            ),
            ExpressionAttributeNames={"#r": "rules"},
            ExpressionAttributeValues={":new_rule": [rule], ":empty": []},
        )
    except DynamoDBError as exc:
        return server_error(str(exc))
    except Exception as exc:
        logger.error("DynamoDB error in create_remediation_rule", extra={"error": str(exc)})
        return server_error(str(exc))

    return ok(rule)


def delete_remediation_rule(
    path_params: dict[str, str],
    _query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """DELETE /remediation/rules/{rule_id} — remove a rule from the global config."""
    rule_id = path_params.get("rule_id", "")
    if not rule_id:
        return bad_request("Missing path parameter: rule_id")

    from backend.functions.remediation_engine.config import load_config
    try:
        config = load_config(_REMEDIATION_CONFIG_TABLE)
    except DynamoDBError as exc:
        return server_error(str(exc))

    rules = config.get("rules", [])
    new_rules = [r for r in rules if r.get("rule_id") != rule_id]

    if len(new_rules) == len(rules):
        return not_found(f"Rule {rule_id!r}")

    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_REMEDIATION_CONFIG_TABLE)
        table.update_item(
            Key={"config_id": _REMEDIATION_CONFIG_ID},
            UpdateExpression="SET #r = :rules",
            ExpressionAttributeNames={"#r": "rules"},
            ExpressionAttributeValues={":rules": new_rules},
        )
    except DynamoDBError as exc:
        return server_error(str(exc))
    except Exception as exc:
        logger.error("DynamoDB error in delete_remediation_rule", extra={"error": str(exc)})
        return server_error(str(exc))

    return ok({"rule_id": rule_id, "deleted": True})


# ===========================================================================
# /remediation/audit
# ===========================================================================

def list_remediation_audit(
    _path_params: dict[str, str],
    query_params: dict[str, str],
    _event: dict[str, Any],
) -> dict[str, Any]:
    """GET /remediation/audit — list audit log entries with optional filters.

    Query params:
      identity_arn  — filter by identity (uses IdentityTimeIndex GSI)
      incident_id   — filter by incident (uses IncidentIndex GSI)
      start_date    — ISO timestamp lower bound (SK range on GSI)
      limit         — max items (default 25, max 100)
      next_token    — pagination cursor
    """
    try:
        limit = parse_limit(query_params)
        start_key = parse_exclusive_start_key(query_params)
    except ValidationError as exc:
        return bad_request(str(exc))

    identity_arn = query_params.get("identity_arn")
    incident_id = query_params.get("incident_id")
    start_date = query_params.get("start_date")

    if identity_arn and incident_id:
        return bad_request(
            "Filtering by both 'identity_arn' and 'incident_id' is not supported. "
            "Use one filter at a time."
        )

    t0 = time.monotonic()
    try:
        dynamodb = get_dynamodb_client()
        table = dynamodb.Table(_REMEDIATION_AUDIT_TABLE)

        if identity_arn:
            # IdentityTimeIndex: PK=identity_arn, SK=timestamp
            key_cond = Key("identity_arn").eq(identity_arn)
            if start_date:
                key_cond = key_cond & Key("timestamp").gte(start_date)
            kwargs: dict[str, Any] = {
                "IndexName": "IdentityTimeIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        elif incident_id:
            # IncidentIndex: PK=incident_id, SK=timestamp
            key_cond = Key("incident_id").eq(incident_id)
            if start_date:
                key_cond = key_cond & Key("timestamp").gte(start_date)
            kwargs = {
                "IndexName": "IncidentIndex",
                "KeyConditionExpression": key_cond,
                "Limit": limit,
            }
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.query(**kwargs)

        else:
            kwargs = {"Limit": limit}
            if start_key:
                kwargs["ExclusiveStartKey"] = start_key
            resp = table.scan(**kwargs)

    except DynamoDBError as exc:
        return server_error(str(exc))

    elapsed = (time.monotonic() - t0) * 1000
    return ok(resp.get("Items", []), resp.get("LastEvaluatedKey"), elapsed)
