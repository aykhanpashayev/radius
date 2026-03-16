"""DynamoDB utility wrappers with retry logic for Radius Lambda functions."""

import time
from typing import Any, Generator

import boto3
from botocore.exceptions import ClientError

from backend.common.errors import DynamoDBError
from backend.common.logging_utils import get_logger

logger = get_logger(__name__)

# Exponential backoff settings
_MAX_RETRIES = 3
_BASE_DELAY_S = 0.1
_RETRYABLE_CODES = {"ProvisionedThroughputExceededException", "RequestLimitExceeded", "ThrottlingException"}


def get_dynamodb_client() -> Any:
    """Return a boto3 DynamoDB client (resource interface)."""
    return boto3.resource("dynamodb")


def _should_retry(error: ClientError) -> bool:
    code = error.response["Error"]["Code"]
    return code in _RETRYABLE_CODES


def _with_retry(fn, *args, **kwargs):
    """Execute *fn* with exponential backoff on retryable DynamoDB errors."""
    last_error: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            return fn(*args, **kwargs)
        except ClientError as exc:
            if _should_retry(exc) and attempt < _MAX_RETRIES - 1:
                delay = _BASE_DELAY_S * (2 ** attempt)
                logger.warning(
                    "DynamoDB retryable error, backing off",
                    extra={"attempt": attempt + 1, "delay_s": delay, "error": str(exc)},
                )
                time.sleep(delay)
                last_error = exc
            else:
                raise DynamoDBError(f"DynamoDB operation failed: {exc}") from exc
    raise DynamoDBError(f"DynamoDB operation failed after {_MAX_RETRIES} retries") from last_error


def put_item(table_name: str, item: dict[str, Any]) -> None:
    """Write an item to a DynamoDB table with retry logic.

    Args:
        table_name: DynamoDB table name.
        item: Item dict to write.

    Raises:
        DynamoDBError: On unrecoverable write failure.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    def _put():
        table.put_item(Item=item)

    _with_retry(_put)


def get_item(table_name: str, key: dict[str, Any]) -> dict[str, Any] | None:
    """Retrieve a single item by primary key.

    Args:
        table_name: DynamoDB table name.
        key: Primary key dict (partition key + optional sort key).

    Returns:
        Item dict or None if not found.

    Raises:
        DynamoDBError: On unrecoverable read failure.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    def _get():
        return table.get_item(Key=key)

    response = _with_retry(_get)
    return response.get("Item")


def update_item(
    table_name: str,
    key: dict[str, Any],
    update_expression: str,
    expression_attribute_values: dict[str, Any],
    expression_attribute_names: dict[str, str] | None = None,
    condition_expression: str | None = None,
) -> dict[str, Any]:
    """Atomically update an item in a DynamoDB table.

    Args:
        table_name: DynamoDB table name.
        key: Primary key dict.
        update_expression: DynamoDB UpdateExpression string.
        expression_attribute_values: Values map for the expression.
        expression_attribute_names: Optional name aliases for reserved words.
        condition_expression: Optional condition to guard the update.

    Returns:
        Updated item attributes.

    Raises:
        DynamoDBError: On unrecoverable update failure.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    kwargs: dict[str, Any] = {
        "Key": key,
        "UpdateExpression": update_expression,
        "ExpressionAttributeValues": expression_attribute_values,
        "ReturnValues": "ALL_NEW",
    }
    if expression_attribute_names:
        kwargs["ExpressionAttributeNames"] = expression_attribute_names
    if condition_expression:
        kwargs["ConditionExpression"] = condition_expression

    def _update():
        return table.update_item(**kwargs)

    response = _with_retry(_update)
    return response.get("Attributes", {})


def query_gsi(
    table_name: str,
    index_name: str,
    key_condition_expression: Any,
    expression_attribute_values: dict[str, Any],
    expression_attribute_names: dict[str, str] | None = None,
    filter_expression: Any | None = None,
    limit: int = 25,
    exclusive_start_key: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Query a GSI with pagination support.

    Args:
        table_name: DynamoDB table name.
        index_name: GSI name.
        key_condition_expression: Boto3 Key condition expression.
        expression_attribute_values: Values map.
        expression_attribute_names: Optional name aliases.
        filter_expression: Optional filter applied after key condition.
        limit: Maximum items to return (1–100).
        exclusive_start_key: Pagination cursor from previous response.

    Returns:
        Tuple of (items list, last_evaluated_key or None).

    Raises:
        DynamoDBError: On unrecoverable query failure.
    """
    dynamodb = get_dynamodb_client()
    table = dynamodb.Table(table_name)

    limit = max(1, min(limit, 100))

    kwargs: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": key_condition_expression,
        "ExpressionAttributeValues": expression_attribute_values,
        "Limit": limit,
    }
    if expression_attribute_names:
        kwargs["ExpressionAttributeNames"] = expression_attribute_names
    if filter_expression is not None:
        kwargs["FilterExpression"] = filter_expression
    if exclusive_start_key:
        kwargs["ExclusiveStartKey"] = exclusive_start_key

    def _query():
        return table.query(**kwargs)

    response = _with_retry(_query)
    return response.get("Items", []), response.get("LastEvaluatedKey")
