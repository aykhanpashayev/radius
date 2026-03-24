"""Shared fixtures for Radius integration tests.

All integration tests run inside a moto mock_aws() context with fake AWS
credentials — no live AWS environment is required.
"""

import os

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
# Session-scoped mock + table creation (created once per test session)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def _mock_aws_session():
    """Start a single moto mock_aws context for the entire test session."""
    # Set credentials at session level (monkeypatch is function-scoped, so use os.environ)
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    with mock_aws():
        yield


@pytest.fixture(scope="session")
def _session_dynamodb_tables(_mock_aws_session):
    """Create all 5 DynamoDB tables once for the entire session."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    _create_identity_profile(dynamodb)
    _create_blast_radius_score(dynamodb)
    _create_incident(dynamodb)
    _create_event_summary(dynamodb)
    _create_trust_relationship(dynamodb)
    return dict(_TABLE_NAMES)


@pytest.fixture(scope="session")
def _session_sns_topic(_session_dynamodb_tables):
    """Create a single SNS topic for the entire session."""
    sns = boto3.client("sns", region_name="us-east-1")
    response = sns.create_topic(Name="test-alert-topic")
    return response["TopicArn"]


def _clear_all_tables():
    """Delete all items from every table between tests."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    for table_name in _TABLE_NAMES.values():
        table = dynamodb.Table(table_name)
        # Determine key schema
        key_names = [k["AttributeName"] for k in table.key_schema]
        scan = table.scan(ProjectionExpression=", ".join(f"#k{i}" for i in range(len(key_names))),
                          ExpressionAttributeNames={f"#k{i}": k for i, k in enumerate(key_names)})
        with table.batch_writer() as batch:
            for item in scan.get("Items", []):
                batch.delete_item(Key={k: item[k] for k in key_names})


# ---------------------------------------------------------------------------
# Function-scoped fixtures — reuse session tables but clear data each test
# ---------------------------------------------------------------------------

@pytest.fixture
def dynamodb_tables(aws_credentials, _session_dynamodb_tables):
    """Yield table names dict; clear all table data before and after each test."""
    _clear_all_tables()
    yield dict(_TABLE_NAMES)
    _clear_all_tables()


# ---------------------------------------------------------------------------
# SNS topic fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sns_topic(dynamodb_tables, _session_sns_topic):
    """Yield the session SNS topic ARN (topic persists; SQS queues are per-test)."""
    yield _session_sns_topic
