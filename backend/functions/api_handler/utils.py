"""Shared utilities for API_Handler: pagination, response formatting, validation."""

import base64
import json
import time
from typing import Any

from backend.common.errors import ValidationError
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

_DEFAULT_LIMIT = 25
_MAX_LIMIT = 100

_CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Allow-Methods": "GET,PATCH,OPTIONS",
}


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------

def encode_next_token(last_evaluated_key: dict[str, Any]) -> str:
    """Encode a DynamoDB LastEvaluatedKey as a base64 next_token."""
    return base64.b64encode(json.dumps(last_evaluated_key, default=str).encode()).decode()


def decode_next_token(token: str) -> dict[str, Any]:
    """Decode a base64 next_token back to a DynamoDB ExclusiveStartKey.

    Raises:
        ValidationError: If the token is malformed.
    """
    try:
        return json.loads(base64.b64decode(token.encode()).decode())
    except Exception as exc:
        raise ValidationError(f"Invalid next_token: {exc}") from exc


def parse_limit(params: dict[str, str]) -> int:
    """Parse and clamp the 'limit' query parameter."""
    raw = params.get("limit", str(_DEFAULT_LIMIT))
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"'limit' must be an integer, got: {raw!r}") from exc
    if value < 1 or value > _MAX_LIMIT:
        raise ValidationError(f"'limit' must be between 1 and {_MAX_LIMIT}, got: {value}")
    return value


def parse_exclusive_start_key(params: dict[str, str]) -> dict[str, Any] | None:
    """Parse the 'next_token' query parameter into an ExclusiveStartKey."""
    token = params.get("next_token")
    if not token:
        return None
    return decode_next_token(token)


# ---------------------------------------------------------------------------
# Response formatting
# ---------------------------------------------------------------------------

def ok(data: list[Any] | dict[str, Any], next_token: dict | None = None,
       query_time_ms: float | None = None) -> dict[str, Any]:
    """Return a 200 response with standard envelope."""
    if isinstance(data, list):
        body: dict[str, Any] = {
            "data": data,
            "metadata": {"count": len(data)},
        }
        if next_token is not None:
            body["metadata"]["next_token"] = encode_next_token(next_token)
        if query_time_ms is not None:
            body["metadata"]["query_time_ms"] = round(query_time_ms, 2)
    else:
        body = data

    return _response(200, body)


def not_found(resource: str) -> dict[str, Any]:
    return _response(404, {"error": "Not Found", "message": f"{resource} not found"})


def bad_request(message: str) -> dict[str, Any]:
    return _response(400, {"error": "Bad Request", "message": message})


def server_error(message: str = "Internal server error") -> dict[str, Any]:
    return _response(500, {"error": "Internal Server Error", "message": message})


def _response(status_code: int, body: Any) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {**_CORS_HEADERS, "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }
