"""Structured JSON logging utilities for Radius Lambda functions."""

import json
import logging
import os
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

_LOG_LEVEL = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

# CloudWatch client for custom metric emission — instantiated lazily so unit
# tests that don't mock boto3 don't fail on import.
_cloudwatch = None
_NAMESPACE = "Radius"


def _get_cloudwatch():
    global _cloudwatch
    if _cloudwatch is None:
        _cloudwatch = boto3.client("cloudwatch")
    return _cloudwatch


def put_metric(
    name: str,
    value: float,
    unit: str = "Count",
    dimensions: dict[str, str] | None = None,
) -> None:
    """Emit a custom CloudWatch metric.

    Swallows all exceptions — metric emission must never crash a handler.

    Args:
        name: Metric name (e.g. "ScoresWritten").
        value: Numeric value.
        unit: CloudWatch unit string (Count, Milliseconds, etc.).
        dimensions: Optional dict of dimension name → value.
    """
    metric: dict[str, Any] = {"MetricName": name, "Value": value, "Unit": unit}
    if dimensions:
        metric["Dimensions"] = [{"Name": k, "Value": v} for k, v in dimensions.items()]
    try:
        _get_cloudwatch().put_metric_data(Namespace=_NAMESPACE, MetricData=[metric])
    except Exception:
        pass  # Never let metric emission crash the handler


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_now(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Merge any extra fields attached to the record
        for key, value in record.__dict__.items():
            if key not in (
                "args", "asctime", "created", "exc_info", "exc_text",
                "filename", "funcName", "id", "levelname", "levelno",
                "lineno", "message", "module", "msecs", "msg", "name",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName",
            ):
                payload[key] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def get_logger(name: str, correlation_id: str | None = None) -> logging.Logger:
    """Return a structured JSON logger.

    Args:
        name: Logger name (typically __name__ of the calling module).
        correlation_id: Optional correlation ID to attach to every record.

    Returns:
        Configured Logger instance.
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(_LOG_LEVEL)
        logger.propagate = False

    if correlation_id:
        logger = logging.LoggerAdapter(logger, {"correlation_id": correlation_id})  # type: ignore[assignment]

    return logger


def generate_correlation_id() -> str:
    """Generate a new UUID v4 correlation ID."""
    return str(uuid.uuid4())


def log_error(
    logger: logging.Logger,
    message: str,
    error: Exception,
    correlation_id: str | None = None,
    **extra: Any,
) -> None:
    """Log an error with structured fields including stack trace.

    Args:
        logger: Logger instance.
        message: Human-readable error description.
        error: The exception that was raised.
        correlation_id: Optional correlation ID for request tracing.
        **extra: Additional key-value pairs to include in the log record.
    """
    fields: dict[str, Any] = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        "stack_trace": traceback.format_exc(),
        **extra,
    }
    if correlation_id:
        fields["correlation_id"] = correlation_id

    logger.error(message, extra=fields, exc_info=True)


def log_request(
    logger: logging.Logger,
    endpoint: str,
    method: str,
    correlation_id: str,
    parameters: dict[str, Any] | None = None,
    response_time_ms: float | None = None,
    status_code: int | None = None,
) -> None:
    """Log an API request with tracing fields.

    Args:
        logger: Logger instance.
        endpoint: API endpoint path.
        method: HTTP method.
        correlation_id: Request correlation ID.
        parameters: Query/path parameters (sanitized).
        response_time_ms: Response time in milliseconds.
        status_code: HTTP response status code.
    """
    fields: dict[str, Any] = {
        "correlation_id": correlation_id,
        "endpoint": endpoint,
        "method": method,
    }
    if parameters is not None:
        fields["parameters"] = parameters
    if response_time_ms is not None:
        fields["response_time_ms"] = round(response_time_ms, 2)
    if status_code is not None:
        fields["status_code"] = status_code

    logger.info("API request", extra=fields)
