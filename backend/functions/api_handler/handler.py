"""API_Handler Lambda — routes API Gateway proxy events to endpoint handlers.

Supports:
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

import time
from typing import Any

from backend.common.errors import ValidationError
from backend.common.logging_utils import generate_correlation_id, get_logger, log_error, log_request
from backend.functions.api_handler import handlers
from backend.functions.api_handler.utils import bad_request, server_error

logger = get_logger(__name__)

# Route table: (method, resource_path_pattern) → handler function
# resource_path uses {param} placeholders matching API Gateway path parameters.
_ROUTES: list[tuple[str, str, Any]] = [
    ("GET",    "/identities",                    handlers.list_identities),
    ("GET",    "/identities/{arn}",              handlers.get_identity),
    ("GET",    "/scores",                        handlers.list_scores),
    ("GET",    "/scores/{arn}",                  handlers.get_score),
    ("GET",    "/incidents",                     handlers.list_incidents),
    ("GET",    "/incidents/{id}",                handlers.get_incident),
    ("PATCH",  "/incidents/{id}",                handlers.patch_incident),
    ("GET",    "/events",                        handlers.list_events),
    ("GET",    "/events/{id}",                   handlers.get_event),
    ("GET",    "/trust-relationships",           handlers.list_trust_relationships),
    ("GET",    "/remediation/config",            handlers.get_remediation_config),
    ("PUT",    "/remediation/config/mode",       handlers.put_remediation_mode),
    ("GET",    "/remediation/rules",             handlers.list_remediation_rules),
    ("POST",   "/remediation/rules",             handlers.create_remediation_rule),
    ("DELETE", "/remediation/rules/{rule_id}",   handlers.delete_remediation_rule),
    ("GET",    "/remediation/audit",             handlers.list_remediation_audit),
]


def _match_route(method: str, resource: str):
    """Return the handler for the given method + resource path, or None."""
    for route_method, route_resource, fn in _ROUTES:
        if route_method == method and route_resource == resource:
            return fn
    return None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Main Lambda entry point — dispatches to endpoint handlers."""
    correlation_id = generate_correlation_id()
    start = time.monotonic()

    method = event.get("httpMethod", "")
    resource = event.get("resource", "")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}

    log = get_logger(__name__, correlation_id)
    log.info("API request received", extra={
        "method": method,
        "resource": resource,
        "path_params": path_params,
        "query_params": query_params,
        "correlation_id": correlation_id,
    })

    handler_fn = _match_route(method, resource)
    if handler_fn is None:
        response = bad_request(f"No route for {method} {resource}")
        _log_response(log, method, resource, correlation_id, response["statusCode"],
                      start, query_params)
        return response

    try:
        response = handler_fn(path_params, query_params, event)
    except ValidationError as exc:
        response = bad_request(str(exc))
    except Exception as exc:
        log_error(log, "Unhandled error in API handler", exc, correlation_id,
                  method=method, resource=resource)
        response = server_error()

    _log_response(log, method, resource, correlation_id, response["statusCode"], start, query_params)
    return response


def _log_response(log, method, resource, correlation_id, status_code, start, params):
    elapsed = (time.monotonic() - start) * 1000
    log_request(log, resource, method, correlation_id,
                parameters=params,
                response_time_ms=elapsed,
                status_code=status_code)
