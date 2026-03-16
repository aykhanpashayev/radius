"""Custom exception classes for Radius Lambda functions."""


class RadiusError(Exception):
    """Base exception for all Radius application errors."""


class ValidationError(RadiusError):
    """Raised when input validation fails (invalid ARN, missing fields, etc.)."""


class DynamoDBError(RadiusError):
    """Raised when a DynamoDB operation fails after retries."""


class EventProcessingError(RadiusError):
    """Raised when a CloudTrail event cannot be processed."""
