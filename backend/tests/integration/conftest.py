"""Shared fixtures for Radius integration tests.

All integration tests run inside a moto mock_aws() context with fake AWS
credentials — no live AWS environment is required.
"""

import boto3
import pytest
from moto import mock_aws


# ---------------------------------------------------------------------------
# AWS credential fixture — autouse so every test gets fake creds
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def aws_credentials(monkeypatch):
    """Set fake boto3 credentials so no live AWS calls are ever made."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


# ---------------------------------------------------------------------------
# Table name constants
# ---------------------------------------------------------------------------

_TABLE_NAMES = {
    "identity_profile": "test-identity-profile",
    "blast_radius_score": "test-blast-radius-score",
    "incident": "test-incident",
    "event_summary": "test-event-summary",
    "trust_relationship": "test-trust-relationship",
}


def table_names() -> dict:
    """Return the standard table name dict used across all test modules."""
    return dict(_TABLE_NAMES)


# ---------------------------------------------------------------------------
# DynamoDB table creation helpers
# ---------------------------------------------------------------------------

def _create_identity_profile(dynamodb):
    dynamodb.create_table(
        TableName=_TABLE_NAMES["identity_profile"],
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "identity_arn", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "identity_arn", "AttributeType": "S"},
            {"AttributeName": "identity_type", "AttributeType": "S"},
            {"AttributeName": "account_id", "AttributeType": "S"},
            {"AttributeName": "last_activity_timestamp", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "IdentityTypeIndex",
                "KeySchema": [
                    {"AttributeName": "identity_type", "KeyType": "HASH"},
                    {"AttributeName": "account_id", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "AccountIndex",
                "KeySchema": [
                    {"AttributeName": "account_id", "KeyType": "HASH"},
                    {"AttributeName": "last_activity_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )


def _create_blast_radius_score(dynamodb):
    dynamodb.create_table(
        TableName=_TABLE_NAMES["blast_radius_score"],
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "identity_arn", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "identity_arn", "AttributeType": "S"},
            {"AttributeName": "severity_level", "AttributeType": "S"},
            {"AttributeName": "score_value", "AttributeType": "N"},
            {"AttributeName": "calculation_timestamp", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "ScoreRangeIndex",
                "KeySchema": [
                    {"AttributeName": "severity_level", "KeyType": "HASH"},
                    {"AttributeName": "score_value", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "SeverityIndex",
                "KeySchema": [
                    {"AttributeName": "severity_level", "KeyType": "HASH"},
                    {"AttributeName": "calculation_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            },
        ],
    )


def _create_incident(dynamodb):
    dynamodb.create_table(
        TableName=_TABLE_NAMES["incident"],
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "incident_id", "KeyType": "HASH"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "incident_id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "severity", "AttributeType": "S"},
            {"AttributeName": "identity_arn", "AttributeType": "S"},
            {"AttributeName": "creation_timestamp", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "StatusIndex",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "creation_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "SeverityIndex",
                "KeySchema": [
                    {"AttributeName": "severity", "KeyType": "HASH"},
                    {"AttributeName": "creation_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                # CRITICAL: KEYS_ONLY to match find_duplicate() in processor.py
                "IndexName": "IdentityIndex",
                "KeySchema": [
                    {"AttributeName": "identity_arn", "KeyType": "HASH"},
                    {"AttributeName": "creation_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            },
        ],
    )


def _create_event_summary(dynamodb):
    dynamodb.create_table(
        TableName=_TABLE_NAMES["event_summary"],
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "identity_arn", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "identity_arn", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "event_id", "AttributeType": "S"},
            {"AttributeName": "event_type", "AttributeType": "S"},
            {"AttributeName": "date_partition", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "EventIdIndex",
                "KeySchema": [
                    {"AttributeName": "event_id", "KeyType": "HASH"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "EventTypeIndex",
                "KeySchema": [
                    {"AttributeName": "event_type", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            },
            {
                "IndexName": "TimeRangeIndex",
                "KeySchema": [
                    {"AttributeName": "date_partition", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )


def _create_trust_relationship(dynamodb):
    dynamodb.create_table(
        TableName=_TABLE_NAMES["trust_relationship"],
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "source_arn", "KeyType": "HASH"},
            {"AttributeName": "target_arn", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "source_arn", "AttributeType": "S"},
            {"AttributeName": "target_arn", "AttributeType": "S"},
            {"AttributeName": "relationship_type", "AttributeType": "S"},
            {"AttributeName": "discovery_timestamp", "AttributeType": "S"},
            {"AttributeName": "target_account_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "RelationshipTypeIndex",
                "KeySchema": [
                    {"AttributeName": "relationship_type", "KeyType": "HASH"},
                    {"AttributeName": "discovery_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "TargetAccountIndex",
                "KeySchema": [
                    {"AttributeName": "target_account_id", "KeyType": "HASH"},
                    {"AttributeName": "discovery_timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            },
        ],
    )


# ---------------------------------------------------------------------------
# DynamoDB tables fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def dynamodb_tables(aws_credentials):
    """Create all 5 DynamoDB tables inside a moto mock context.

    Yields a dict of logical name → table name. The mock_aws() context is
    torn down on exit (even on test failure) via yield inside the with block.
    """
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        _create_identity_profile(dynamodb)
        _create_blast_radius_score(dynamodb)
        _create_incident(dynamodb)
        _create_event_summary(dynamodb)
        _create_trust_relationship(dynamodb)
        yield dict(_TABLE_NAMES)


# ---------------------------------------------------------------------------
# SNS topic fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sns_topic(dynamodb_tables):
    """Create a mocked SNS topic and yield its ARN."""
    sns = boto3.client("sns", region_name="us-east-1")
    response = sns.create_topic(Name="test-alert-topic")
    yield response["TopicArn"]
