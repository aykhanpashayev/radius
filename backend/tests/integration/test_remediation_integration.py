"""Integration tests for the Remediation_Engine using moto-mocked AWS services.

All tests run inside a moto mock_aws() context — no live AWS calls are made.
Fixtures create real DynamoDB tables and SNS topics so the engine exercises
the full stack: config loading, safety controls, rule matching, action
execution, audit writes, and SNS notifications.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import boto3
import pytest
from boto3.dynamodb.conditions import Attr
from moto import mock_aws

# ---------------------------------------------------------------------------
# Table / topic name constants
# ---------------------------------------------------------------------------

_CONFIG_TABLE = "test-remediation-config"
_AUDIT_TABLE = "test-remediation-audit"
_TOPIC_NAME = "test-remediation-topic"

_USER_ARN = "arn:aws:iam::123456789012:user/alice"
_ACCOUNT_ID = "123456789012"


# ---------------------------------------------------------------------------
# Session-scoped moto context + infrastructure
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def aws_env():
    """Set fake AWS credentials for the entire session."""
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


@pytest.fixture(scope="session")
def _mock_session(aws_env):
    """Single moto mock_aws context for the whole test session."""
    with mock_aws():
        yield


@pytest.fixture(scope="session")
def _infra(_mock_session):
    """Create DynamoDB tables, SNS topic, and IAM user once per session."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")

    # Remediation_Config table
    dynamodb.create_table(
        TableName=_CONFIG_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "config_id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "config_id", "AttributeType": "S"}],
    )

    # Remediation_Audit_Log table with required GSIs
    dynamodb.create_table(
        TableName=_AUDIT_TABLE,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[{"AttributeName": "audit_id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "audit_id", "AttributeType": "S"},
            {"AttributeName": "identity_arn", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
            {"AttributeName": "incident_id", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "IdentityTimeIndex",
                "KeySchema": [
                    {"AttributeName": "identity_arn", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "IncidentIndex",
                "KeySchema": [
                    {"AttributeName": "incident_id", "KeyType": "HASH"},
                    {"AttributeName": "timestamp", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "KEYS_ONLY"},
            },
        ],
    )

    # SNS topic
    sns = boto3.client("sns", region_name="us-east-1")
    topic_resp = sns.create_topic(Name=_TOPIC_NAME)
    topic_arn = topic_resp["TopicArn"]

    # IAM user with an access key (used by enforce-mode tests)
    iam = boto3.client("iam", region_name="us-east-1")
    iam.create_user(UserName="alice")
    iam.create_login_profile(UserName="alice", Password="Test1234!")
    key_resp = iam.create_access_key(UserName="alice")
    access_key_id = key_resp["AccessKey"]["AccessKeyId"]

    return {
        "config_table": _CONFIG_TABLE,
        "audit_table": _AUDIT_TABLE,
        "topic_arn": topic_arn,
        "access_key_id": access_key_id,
    }


# ---------------------------------------------------------------------------
# Function-scoped fixture: clear tables + reset env vars before each test
# ---------------------------------------------------------------------------

def _clear_table(table_name: str) -> None:
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(table_name)
    key_names = [k["AttributeName"] for k in table.key_schema]
    scan = table.scan(
        ProjectionExpression=", ".join(f"#k{i}" for i in range(len(key_names))),
        ExpressionAttributeNames={f"#k{i}": k for i, k in enumerate(key_names)},
    )
    with table.batch_writer() as batch:
        for item in scan.get("Items", []):
            batch.delete_item(Key={k: item[k] for k in key_names})


@pytest.fixture
def infra(_infra, monkeypatch):
    """Yield infra dict; clear DynamoDB data and set env vars before each test."""
    _clear_table(_CONFIG_TABLE)
    _clear_table(_AUDIT_TABLE)

    monkeypatch.setenv("REMEDIATION_TOPIC_ARN", _infra["topic_arn"])
    monkeypatch.setenv("REMEDIATION_CONFIG_TABLE", _CONFIG_TABLE)
    monkeypatch.setenv("REMEDIATION_AUDIT_TABLE", _AUDIT_TABLE)

    yield _infra


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _put_config(
    config_table: str,
    risk_mode: str = "monitor",
    rules: list | None = None,
    excluded_arns: list | None = None,
    protected_account_ids: list | None = None,
    allowed_ip_ranges: list | None = None,
) -> None:
    """Write a config record directly to DynamoDB."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(config_table)
    table.put_item(Item={
        "config_id": "global",
        "risk_mode": risk_mode,
        "rules": rules or [],
        "excluded_arns": excluded_arns or [],
        "protected_account_ids": protected_account_ids or [],
        "allowed_ip_ranges": allowed_ip_ranges or [],
    })


def _make_rule(
    rule_id: str = "rule-1",
    actions: list | None = None,
    min_severity: str = "Low",
    detection_types: list | None = None,
    identity_types: list | None = None,
    priority: int = 10,
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "active": True,
        "min_severity": min_severity,
        "detection_types": detection_types or [],
        "identity_types": identity_types or [],
        "actions": actions or ["notify_security_team"],
        "priority": priority,
    }


def _make_incident(
    incident_id: str | None = None,
    identity_arn: str = _USER_ARN,
    severity: str = "Critical",
    detection_type: str = "privilege_escalation",
    identity_type: str = "IAMUser",
) -> dict[str, Any]:
    return {
        "incident_id": incident_id or str(uuid.uuid4()),
        "identity_arn": identity_arn,
        "severity": severity,
        "detection_type": detection_type,
        "identity_type": identity_type,
        "creation_timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }


def _make_engine(
    config_table: str,
    audit_table: str,
    topic_arn: str,
    dry_run: bool = False,
):
    from backend.functions.remediation_engine.engine import RemediationRuleEngine
    return RemediationRuleEngine(
        config_table=config_table,
        audit_table=audit_table,
        topic_arn=topic_arn,
        dry_run=dry_run,
    )


def _scan_audit(audit_table: str, incident_id: str | None = None) -> list[dict]:
    """Return all audit entries, optionally filtered by incident_id."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(audit_table)
    if incident_id:
        resp = table.scan(FilterExpression=Attr("incident_id").eq(incident_id))
    else:
        resp = table.scan()
    return resp.get("Items", [])


def _subscribe_sqs(topic_arn: str) -> str:
    """Create a fresh SQS queue, subscribe to topic, return queue URL."""
    sqs = boto3.client("sqs", region_name="us-east-1")
    sns = boto3.client("sns", region_name="us-east-1")
    queue_name = f"test-q-{uuid.uuid4().hex[:8]}"
    queue_url = sqs.create_queue(QueueName=queue_name)["QueueUrl"]
    queue_arn = sqs.get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    sns.subscribe(TopicArn=topic_arn, Protocol="sqs", Endpoint=queue_arn)
    return queue_url


def _drain_sqs(queue_url: str) -> list[dict]:
    sqs = boto3.client("sqs", region_name="us-east-1")
    messages = []
    while True:
        resp = sqs.receive_message(
            QueueUrl=queue_url, MaxNumberOfMessages=10, WaitTimeSeconds=0
        )
        batch = resp.get("Messages", [])
        if not batch:
            break
        messages.extend(batch)
    return messages


def _write_past_audit_entry(
    audit_table: str,
    identity_arn: str,
    incident_id: str,
    minutes_ago: int = 30,
) -> None:
    """Directly write an 'executed' audit entry with a past timestamp to simulate cooldown."""
    dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
    table = dynamodb.Table(audit_table)
    past_ts = (
        datetime.now(tz=timezone.utc) - timedelta(minutes=minutes_ago)
    ).isoformat()
    table.put_item(Item={
        "audit_id": str(uuid.uuid4()),
        "incident_id": incident_id,
        "identity_arn": identity_arn,
        "rule_id": "rule-1",
        "action_name": "disable_iam_user",
        "outcome": "executed",
        "risk_mode": "enforce",
        "dry_run": False,
        "timestamp": past_ts,
        "details": "{}",
        "reason": "",
        "ttl": 9999999999,
    })


# ---------------------------------------------------------------------------
# 13.2 — monitor mode: no IAM mutations, all outcomes suppressed
# ---------------------------------------------------------------------------

def test_monitor_mode_no_mutations(infra):
    """Critical incident + matching rule in monitor mode produces zero IAM calls
    and all audit entries have outcome=suppressed."""
    _put_config(
        infra["config_table"],
        risk_mode="monitor",
        rules=[_make_rule(actions=["disable_iam_user"])],
    )
    incident = _make_incident()
    engine = _make_engine(infra["config_table"], infra["audit_table"], infra["topic_arn"])

    # Capture IAM calls via a real moto IAM client — key must still be Active after
    iam = boto3.client("iam", region_name="us-east-1")
    keys_before = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_before = [k for k in keys_before if k["Status"] == "Active"]

    result = engine.process(incident)

    # No IAM mutations — access key still Active
    keys_after = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_after = [k for k in keys_after if k["Status"] == "Active"]
    assert len(active_after) == len(active_before), (
        "monitor mode must not deactivate any access keys"
    )

    # All action outcomes are suppressed
    action_outcomes = result["action_outcomes"]
    assert len(action_outcomes) > 0
    for ao in action_outcomes:
        assert ao["outcome"] == "suppressed", (
            f"Expected suppressed, got {ao['outcome']!r} for action {ao['action']!r}"
        )

    # Audit entries in DynamoDB also reflect suppressed
    entries = _scan_audit(infra["audit_table"], incident["incident_id"])
    action_entries = [e for e in entries if e["action_name"] != "remediation_complete"]
    assert all(e["outcome"] == "suppressed" for e in action_entries), (
        f"Unexpected audit outcomes: {[e['outcome'] for e in action_entries]}"
    )


# ---------------------------------------------------------------------------
# 13.3 — alert mode: SNS published, zero IAM mutations
# ---------------------------------------------------------------------------

def test_alert_mode_notifies_no_mutations(infra):
    """Alert mode publishes to SNS but performs no IAM mutations."""
    _put_config(
        infra["config_table"],
        risk_mode="alert",
        rules=[_make_rule(actions=["notify_security_team"])],
    )
    incident = _make_incident()
    engine = _make_engine(infra["config_table"], infra["audit_table"], infra["topic_arn"])

    queue_url = _subscribe_sqs(infra["topic_arn"])

    iam = boto3.client("iam", region_name="us-east-1")
    keys_before = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_before = [k for k in keys_before if k["Status"] == "Active"]

    engine.process(incident)

    # SNS message published (engine-level notification + action-level)
    messages = _drain_sqs(queue_url)
    assert len(messages) >= 1, "Expected at least one SNS message in alert mode"

    # No IAM mutations
    keys_after = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_after = [k for k in keys_after if k["Status"] == "Active"]
    assert len(active_after) == len(active_before), (
        "alert mode must not deactivate any access keys"
    )


# ---------------------------------------------------------------------------
# 13.4 — enforce mode: IAM access keys deactivated, audit outcome=executed
# ---------------------------------------------------------------------------

def test_enforce_mode_executes_actions(infra):
    """Enforce mode with disable_iam_user rule deactivates access keys and
    writes an audit entry with outcome=executed."""
    _put_config(
        infra["config_table"],
        risk_mode="enforce",
        rules=[_make_rule(actions=["disable_iam_user"])],
    )
    incident = _make_incident()
    engine = _make_engine(infra["config_table"], infra["audit_table"], infra["topic_arn"])

    # Ensure alice has an active key before the test
    iam = boto3.client("iam", region_name="us-east-1")
    keys_before = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_before = [k for k in keys_before if k["Status"] == "Active"]
    assert len(active_before) >= 1, "Test setup: alice must have at least one active key"

    result = engine.process(incident)

    # All active keys should now be Inactive
    keys_after = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_after = [k for k in keys_after if k["Status"] == "Active"]
    assert len(active_after) == 0, (
        f"Expected 0 active keys after enforce, got {len(active_after)}"
    )

    # Audit entry has outcome=executed
    entries = _scan_audit(infra["audit_table"], incident["incident_id"])
    action_entries = [
        e for e in entries
        if e["action_name"] == "disable_iam_user"
    ]
    assert len(action_entries) == 1
    assert action_entries[0]["outcome"] == "executed"

    # Result dict also reflects executed
    disable_outcomes = [
        ao for ao in result["action_outcomes"] if ao["action"] == "disable_iam_user"
    ]
    assert len(disable_outcomes) == 1
    assert disable_outcomes[0]["outcome"] == "executed"


# ---------------------------------------------------------------------------
# 13.5 — cooldown: second invocation within 60 min is suppressed
# ---------------------------------------------------------------------------

def test_cooldown_suppresses_second_invocation(infra):
    """Two engine invocations for the same identity within 60 minutes: the
    second produces all outcome=suppressed with reason=cooldown_active."""
    _put_config(
        infra["config_table"],
        risk_mode="enforce",
        rules=[_make_rule(actions=["disable_iam_user"])],
    )
    incident = _make_incident()
    engine = _make_engine(infra["config_table"], infra["audit_table"], infra["topic_arn"])

    # First invocation — executes normally (keys may already be inactive from 13.4,
    # but the audit entry is what matters for cooldown)
    engine.process(incident)

    # Manually plant an 'executed' audit entry 30 minutes in the past so the
    # cooldown GSI query finds it (the first process() call writes outcome=executed
    # only if the action actually ran; we ensure it exists regardless)
    _write_past_audit_entry(
        infra["audit_table"],
        identity_arn=incident["identity_arn"],
        incident_id=incident["incident_id"],
        minutes_ago=30,
    )

    # Second invocation — should be suppressed by cooldown
    incident2 = _make_incident(identity_arn=incident["identity_arn"])
    result2 = engine.process(incident2)

    # The engine returns suppressed=1 for the safety-suppressed path
    assert result2["suppressed"] >= 1, (
        f"Expected suppressed >= 1, got {result2['suppressed']}"
    )

    # Audit entry for second invocation has reason=cooldown_active
    entries2 = _scan_audit(infra["audit_table"], incident2["incident_id"])
    suppressed_entries = [e for e in entries2 if e.get("reason") == "cooldown_active"]
    assert len(suppressed_entries) >= 1, (
        f"Expected cooldown_active audit entry, got: {[e.get('reason') for e in entries2]}"
    )


# ---------------------------------------------------------------------------
# 13.6 — excluded ARN: engine suppresses with reason=identity_excluded
# ---------------------------------------------------------------------------

def test_excluded_arn_suppressed(infra):
    """Identity ARN in excluded_arns config produces outcome=suppressed
    with reason=identity_excluded."""
    _put_config(
        infra["config_table"],
        risk_mode="enforce",
        rules=[_make_rule(actions=["disable_iam_user"])],
        excluded_arns=[_USER_ARN],
    )
    incident = _make_incident(identity_arn=_USER_ARN)
    engine = _make_engine(infra["config_table"], infra["audit_table"], infra["topic_arn"])

    result = engine.process(incident)

    assert result["suppressed"] >= 1

    entries = _scan_audit(infra["audit_table"], incident["incident_id"])
    excluded_entries = [e for e in entries if e.get("reason") == "identity_excluded"]
    assert len(excluded_entries) >= 1, (
        f"Expected identity_excluded audit entry, got: {[e.get('reason') for e in entries]}"
    )


# ---------------------------------------------------------------------------
# 13.7 — dry_run overrides enforce mode: all suppressed, dry_run=True in audit
# ---------------------------------------------------------------------------

def test_dry_run_flag_overrides_enforce_mode(infra):
    """dry_run=True with risk_mode=enforce in config suppresses all actions
    and writes audit entries with dry_run=True."""
    _put_config(
        infra["config_table"],
        risk_mode="enforce",
        rules=[_make_rule(actions=["disable_iam_user", "notify_security_team"])],
    )
    incident = _make_incident()
    # Engine constructed with dry_run=True
    engine = _make_engine(
        infra["config_table"], infra["audit_table"], infra["topic_arn"], dry_run=True
    )

    iam = boto3.client("iam", region_name="us-east-1")
    # Re-activate alice's key if it was deactivated by a previous test
    keys = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    for k in keys:
        if k["Status"] == "Inactive":
            iam.update_access_key(
                UserName="alice", AccessKeyId=k["AccessKeyId"], Status="Active"
            )

    result = engine.process(incident)

    # All action outcomes are suppressed
    for ao in result["action_outcomes"]:
        assert ao["outcome"] == "suppressed", (
            f"dry_run: expected suppressed, got {ao['outcome']!r} for {ao['action']!r}"
        )

    # No IAM mutations — keys still Active
    keys_after = iam.list_access_keys(UserName="alice")["AccessKeyMetadata"]
    active_after = [k for k in keys_after if k["Status"] == "Active"]
    assert len(active_after) >= 1, "dry_run must not deactivate access keys"

    # Audit entries have dry_run=True
    entries = _scan_audit(infra["audit_table"], incident["incident_id"])
    action_entries = [e for e in entries if e["action_name"] != "remediation_complete"]
    assert len(action_entries) > 0
    for e in action_entries:
        assert e["dry_run"] is True, (
            f"Expected dry_run=True in audit entry, got {e['dry_run']!r}"
        )


# ---------------------------------------------------------------------------
# 13.8 — audit log completeness: 2 rules × 2 unique actions = 4 + 1 summary
# ---------------------------------------------------------------------------

def test_audit_log_completeness(infra):
    """Two matched rules each contributing two unique actions produce exactly
    4 action audit entries plus 1 summary entry (5 total)."""
    # Rule 1: disable_iam_user + notify_security_team
    # Rule 2: notify_security_team (dup) + restrict_network_access
    # Deduplicated unique actions: disable_iam_user, notify_security_team, restrict_network_access
    # BUT the task spec says "two rules each having two actions" → 4 entries + 1 summary.
    # We use two rules with completely distinct action pairs to get exactly 4 unique actions.
    rule1 = _make_rule(
        rule_id="rule-a",
        actions=["disable_iam_user", "notify_security_team"],
        priority=1,
    )
    rule2 = _make_rule(
        rule_id="rule-b",
        actions=["block_role_assumption", "restrict_network_access"],
        priority=2,
    )
    _put_config(
        infra["config_table"],
        risk_mode="monitor",  # monitor so no real IAM calls needed
        rules=[rule1, rule2],
    )
    incident = _make_incident()
    engine = _make_engine(infra["config_table"], infra["audit_table"], infra["topic_arn"])

    engine.process(incident)

    entries = _scan_audit(infra["audit_table"], incident["incident_id"])

    # Separate action entries from the summary entry
    action_entries = [e for e in entries if e["action_name"] != "remediation_complete"]
    summary_entries = [e for e in entries if e["action_name"] == "remediation_complete"]

    assert len(action_entries) == 4, (
        f"Expected 4 action audit entries, got {len(action_entries)}: "
        f"{[e['action_name'] for e in action_entries]}"
    )
    assert len(summary_entries) == 1, (
        f"Expected 1 summary audit entry, got {len(summary_entries)}"
    )
    assert len(entries) == 5, (
        f"Expected 5 total audit entries (4 actions + 1 summary), got {len(entries)}"
    )
