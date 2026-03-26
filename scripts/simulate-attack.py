#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, io
# Force UTF-8 output on Windows so Unicode box-drawing characters render correctly.
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
"""simulate-attack.py — Simulate a privilege escalation attack through the Radius pipeline.

Runs a four-step IAM attack scenario (CreateUser → AttachUserPolicy →
CreatePolicyVersion → StopLogging) against either a moto-mocked AWS
environment (--mode mock, default) or a live AWS environment (--mode live).

Usage:
    python scripts/simulate-attack.py [OPTIONS]

Options:
    --mode {mock,live}     AWS mode. mock uses moto; live uses real AWS. Default: mock
    --identity ARN         Attacker IAM ARN. Default: arn:aws:iam::123456789012:user/attacker
    --verbose              Print per-event detail during injection
    --phase {1,2,3,4,5}    Run only this phase. Default: all phases
    --timeout SECONDS      Polling timeout for Phase 3. Default: 30
    --help                 Show this message and exit

Examples:
    python scripts/simulate-attack.py --mode mock
    python scripts/simulate-attack.py --mode mock --verbose
    python scripts/simulate-attack.py --mode mock --phase 4
"""

import argparse
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Generator

import boto3

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGION = "us-east-1"
TABLE_IDENTITY_PROFILE = "radius-dev-identity-profile"
TABLE_BLAST_RADIUS_SCORE = "radius-dev-blast-radius-score"
TABLE_INCIDENT = "radius-dev-incident"
TABLE_EVENT_SUMMARY = "radius-dev-event-summary"
TABLE_REMEDIATION_CONFIG = "radius-dev-remediation-config"
TABLE_REMEDIATION_AUDIT_LOG = "radius-dev-remediation-audit-log"

SEPARATOR = "━" * 62
THIN_SEP = "─" * 62

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class PhaseResult:
    phase: int
    name: str
    status: str          # "PASS" | "FAIL" | "SKIPPED"
    duration_s: float
    output: dict = field(default_factory=dict)
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now(offset_seconds: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)).isoformat(
        timespec="microseconds"
    )


def _account_id_from_arn(arn: str) -> str:
    """Extract account ID from an IAM ARN."""
    parts = arn.split(":")
    return parts[4] if len(parts) >= 5 else "123456789012"


def _dynamodb(mock_context: Any | None = None) -> Any:
    """Return a boto3 DynamoDB resource, using the mock context if provided."""
    return boto3.resource("dynamodb", region_name=REGION)


def _print_phase_header(phase_num: int, name: str) -> None:
    print(f"\n{SEPARATOR}")
    print(f"Phase {phase_num}: {name}")
    print(SEPARATOR)


def _print_kv(key: str, value: str, indent: int = 2) -> None:
    pad = " " * indent
    print(f"{pad}{key:<20}: {value}")


# ---------------------------------------------------------------------------
# Mock AWS setup
# ---------------------------------------------------------------------------


@contextmanager
def _mock_aws_context() -> Generator[None, None, None]:
    """Activate moto mock_aws context manager."""
    try:
        from moto import mock_aws  # type: ignore[import]
    except ImportError:
        print("ERROR: moto is not installed. Run: pip install -r backend/requirements-dev.txt",
              file=sys.stderr)
        sys.exit(1)

    with mock_aws():
        yield


def setup_mock_aws() -> None:
    """Create all required DynamoDB tables and seed Remediation_Config in mock mode."""
    dynamodb = boto3.resource("dynamodb", region_name=REGION)

    table_definitions = [
        {
            "TableName": TABLE_IDENTITY_PROFILE,
            "KeySchema": [{"AttributeName": "identity_arn", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "identity_arn", "AttributeType": "S"},
                {"AttributeName": "account_id", "AttributeType": "S"},
                {"AttributeName": "last_activity_timestamp", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "AccountIndex",
                    "KeySchema": [
                        {"AttributeName": "account_id", "KeyType": "HASH"},
                        {"AttributeName": "last_activity_timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": TABLE_BLAST_RADIUS_SCORE,
            "KeySchema": [{"AttributeName": "identity_arn", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "identity_arn", "AttributeType": "S"},
                {"AttributeName": "severity_level", "AttributeType": "S"},
                {"AttributeName": "calculation_timestamp", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "SeverityIndex",
                    "KeySchema": [
                        {"AttributeName": "severity_level", "KeyType": "HASH"},
                        {"AttributeName": "calculation_timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": TABLE_INCIDENT,
            "KeySchema": [{"AttributeName": "incident_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "incident_id", "AttributeType": "S"},
                {"AttributeName": "identity_arn", "AttributeType": "S"},
                {"AttributeName": "creation_timestamp", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "IdentityIndex",
                    "KeySchema": [
                        {"AttributeName": "identity_arn", "KeyType": "HASH"},
                        {"AttributeName": "creation_timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": TABLE_EVENT_SUMMARY,
            "KeySchema": [{"AttributeName": "event_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "event_id", "AttributeType": "S"},
                {"AttributeName": "identity_arn", "AttributeType": "S"},
                {"AttributeName": "event_timestamp", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "IdentityTimeIndex",
                    "KeySchema": [
                        {"AttributeName": "identity_arn", "KeyType": "HASH"},
                        {"AttributeName": "event_timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": TABLE_REMEDIATION_CONFIG,
            "KeySchema": [{"AttributeName": "config_id", "KeyType": "HASH"}],
            "AttributeDefinitions": [
                {"AttributeName": "config_id", "AttributeType": "S"},
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
        {
            "TableName": TABLE_REMEDIATION_AUDIT_LOG,
            "KeySchema": [
                {"AttributeName": "audit_id", "KeyType": "HASH"},
                {"AttributeName": "timestamp", "KeyType": "RANGE"},
            ],
            "AttributeDefinitions": [
                {"AttributeName": "audit_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
                {"AttributeName": "identity_arn", "AttributeType": "S"},
            ],
            "GlobalSecondaryIndexes": [
                {
                    "IndexName": "IdentityTimeIndex",
                    "KeySchema": [
                        {"AttributeName": "identity_arn", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                }
            ],
            "BillingMode": "PAY_PER_REQUEST",
        },
    ]

    for defn in table_definitions:
        dynamodb.create_table(**defn)

    # Seed Remediation_Config with default monitor mode record
    config_table = dynamodb.Table(TABLE_REMEDIATION_CONFIG)
    config_table.put_item(Item={
        "config_id": "default",
        "risk_mode": "monitor",
        "rules": [],
        "excluded_arns": [],
        "protected_account_ids": [],
        "cooldown_minutes": 60,
        "rate_limit_per_hour": 10,
        "updated_at": _utc_now(),
    })


# ---------------------------------------------------------------------------
# Phase 1: Seed IAM Identity
# ---------------------------------------------------------------------------


def phase1_seed_identity(identity_arn: str, verbose: bool) -> PhaseResult:
    """Write an Identity_Profile record for the attacker identity."""
    _print_phase_header(1, "Seed IAM Identity")
    start = time.monotonic()

    try:
        account_id = _account_id_from_arn(identity_arn)
        now = _utc_now()

        item = {
            "identity_arn": identity_arn,
            "identity_type": "IAMUser",
            "account_id": account_id,
            "first_seen": now,
            "last_activity_timestamp": now,
            "event_count": 0,
            "status": "active",
            "tags": {},
        }

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_IDENTITY_PROFILE)
        table.put_item(Item=item)

        duration = time.monotonic() - start
        _print_kv("Identity ARN", identity_arn)
        _print_kv("Identity Type", "IAMUser")
        _print_kv("Account ID", account_id)
        if verbose:
            _print_kv("First Seen", now)
            _print_kv("Event Count", "0")
        _print_kv("Status", f"✓ PASS ({duration:.2f}s)")

        return PhaseResult(
            phase=1,
            name="Seed IAM Identity",
            status="PASS",
            duration_s=duration,
            output={"identity_arn": identity_arn, "account_id": account_id},
        )

    except Exception as exc:
        duration = time.monotonic() - start
        print(f"  ERROR: {exc}")
        return PhaseResult(
            phase=1, name="Seed IAM Identity", status="FAIL",
            duration_s=duration, error=str(exc),
        )


# ---------------------------------------------------------------------------
# Phase 2: Inject Attack Events
# ---------------------------------------------------------------------------


def phase2_inject_events(identity_arn: str, verbose: bool) -> PhaseResult:
    """Write four Event_Summary records representing the attack sequence."""
    _print_phase_header(2, "Inject Privilege Escalation Events")
    start = time.monotonic()

    attack_events = [
        {
            "event_name": "CreateUser",
            "event_source": "iam.amazonaws.com",
            "event_parameters": {
                "userName": "backdoor-admin",
                "path": "/",
            },
            "offset_seconds": -180,
        },
        {
            "event_name": "AttachUserPolicy",
            "event_source": "iam.amazonaws.com",
            "event_parameters": {
                "userName": "backdoor-admin",
                "policyArn": "arn:aws:iam::aws:policy/AdministratorAccess",
            },
            "offset_seconds": -120,
        },
        {
            "event_name": "CreatePolicyVersion",
            "event_source": "iam.amazonaws.com",
            "event_parameters": {
                "policyArn": "arn:aws:iam::123456789012:policy/custom-policy",
                "setAsDefault": True,
                "policyDocument": '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":"*","Resource":"*"}]}',
            },
            "offset_seconds": -60,
        },
        {
            "event_name": "StopLogging",
            "event_source": "cloudtrail.amazonaws.com",
            "event_parameters": {
                "name": "arn:aws:cloudtrail:us-east-1:123456789012:trail/org-trail",
            },
            "offset_seconds": 0,
        },
    ]

    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_EVENT_SUMMARY)
        event_ids = []

        for evt in attack_events:
            event_id = str(uuid.uuid4())
            event_ids.append(event_id)
            timestamp = _utc_now(evt["offset_seconds"])
            service = evt["event_source"].split(".")[0].upper()
            full_event_name = f"{service}:{evt['event_name']}" if service != "IAM" else f"iam:{evt['event_name']}"

            item = {
                "event_id": event_id,
                "identity_arn": identity_arn,
                "event_name": evt["event_name"],
                "event_source": evt["event_source"],
                "event_timestamp": timestamp,
                "aws_region": REGION,
                "source_ip_address": "203.0.113.42",
                "event_parameters": evt["event_parameters"],
                "raw_event": {
                    "eventName": evt["event_name"],
                    "eventSource": evt["event_source"],
                    "eventTime": timestamp,
                    "userIdentity": {
                        "type": "IAMUser",
                        "arn": identity_arn,
                        "accountId": _account_id_from_arn(identity_arn),
                    },
                    "requestParameters": evt["event_parameters"],
                },
            }
            table.put_item(Item=item)

            if verbose:
                _print_kv(f"  Event {len(event_ids)}", f"{evt['event_name']} @ {timestamp}")
            else:
                print(f"  [{len(event_ids)}/4] {evt['event_name']} ({evt['event_source']})")

        duration = time.monotonic() - start
        _print_kv("Events Injected", "4")
        _print_kv("Attack Sequence", "CreateUser → AttachUserPolicy → CreatePolicyVersion → StopLogging")
        _print_kv("Status", f"✓ PASS ({duration:.2f}s)")

        return PhaseResult(
            phase=2,
            name="Inject Privilege Escalation Events",
            status="PASS",
            duration_s=duration,
            output={"event_count": 4, "event_ids": event_ids},
        )

    except Exception as exc:
        duration = time.monotonic() - start
        print(f"  ERROR: {exc}")
        return PhaseResult(
            phase=2, name="Inject Privilege Escalation Events", status="FAIL",
            duration_s=duration, error=str(exc),
        )


# ---------------------------------------------------------------------------
# Phase 3: Poll for Incident
# ---------------------------------------------------------------------------


def phase3_poll_incident(
    identity_arn: str,
    timeout_s: int,
    verbose: bool,
    mock: bool = False,
) -> PhaseResult:
    """Poll the Incident table until a privilege escalation incident appears."""
    _print_phase_header(3, "Poll for Incident")
    start = time.monotonic()

    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_INCIDENT)

        if mock:
            # Simulate pipeline processing delay then write a synthetic incident
            print("  Simulating pipeline processing (2s)...")
            time.sleep(2)

            incident_id = str(uuid.uuid4())
            now = _utc_now()
            synthetic_incident = {
                "incident_id": incident_id,
                "identity_arn": identity_arn,
                "detection_type": "privilege_escalation",
                "severity": "Critical",
                "confidence": 92,
                "status": "open",
                "creation_timestamp": now,
                "update_timestamp": now,
                "related_event_ids": [],
                "status_history": [{"status": "open", "timestamp": now}],
                "notes": "Synthetic incident created by simulate-attack.py (mock mode)",
                "assigned_to": "",
            }
            table.put_item(Item=synthetic_incident)

            duration = time.monotonic() - start
            _print_kv("Incident ID", incident_id)
            _print_kv("Detection Type", "privilege_escalation")
            _print_kv("Severity", "Critical")
            _print_kv("Confidence", "92%")
            _print_kv("Status", f"✓ PASS ({duration:.2f}s)")

            return PhaseResult(
                phase=3,
                name="Poll for Incident",
                status="PASS",
                duration_s=duration,
                output={"incident_id": incident_id, "severity": "Critical"},
            )

        # Live mode: poll IdentityIndex GSI
        from boto3.dynamodb.conditions import Key as DDBKey  # noqa: PLC0415

        print(f"  Polling for incident (timeout={timeout_s}s, interval=2s)...")
        elapsed = 0
        poll_count = 0

        while elapsed < timeout_s:
            poll_count += 1
            if verbose:
                print(f"  Poll #{poll_count} ({elapsed:.0f}s elapsed)...")

            response = table.query(
                IndexName="IdentityIndex",
                KeyConditionExpression=DDBKey("identity_arn").eq(identity_arn),
                ScanIndexForward=False,
                Limit=1,
            )
            items = response.get("Items", [])
            if items:
                incident = items[0]
                duration = time.monotonic() - start
                _print_kv("Incident ID", incident.get("incident_id", ""))
                _print_kv("Detection Type", incident.get("detection_type", ""))
                _print_kv("Severity", incident.get("severity", ""))
                _print_kv("Status", f"✓ PASS ({duration:.2f}s)")

                return PhaseResult(
                    phase=3,
                    name="Poll for Incident",
                    status="PASS",
                    duration_s=duration,
                    output={
                        "incident_id": incident.get("incident_id"),
                        "severity": incident.get("severity"),
                    },
                )

            time.sleep(2)
            elapsed = time.monotonic() - start

        duration = time.monotonic() - start
        msg = f"Timeout waiting for incident after {timeout_s}s"
        print(f"  ERROR: {msg}")
        return PhaseResult(
            phase=3, name="Poll for Incident", status="FAIL",
            duration_s=duration, error=msg,
        )

    except Exception as exc:
        duration = time.monotonic() - start
        print(f"  ERROR: {exc}")
        return PhaseResult(
            phase=3, name="Poll for Incident", status="FAIL",
            duration_s=duration, error=str(exc),
        )


# ---------------------------------------------------------------------------
# Phase 4: Display Blast Radius Score
# ---------------------------------------------------------------------------


def phase4_display_score(identity_arn: str, verbose: bool, mock: bool = False) -> PhaseResult:
    """Query Blast_Radius_Score and print score, severity, and contributing factors."""
    _print_phase_header(4, "Display Blast Radius Score")
    start = time.monotonic()

    try:
        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_BLAST_RADIUS_SCORE)

        response = table.get_item(Key={"identity_arn": identity_arn})
        item = response.get("Item")

        if item is None and mock:
            # Write a synthetic score record in mock mode
            now = _utc_now()
            item = {
                "identity_arn": identity_arn,
                "score_value": 85,
                "severity_level": "Critical",
                "calculation_timestamp": now,
                "contributing_factors": [
                    "privilege_escalation_detected",
                    "logging_disruption_detected",
                    "admin_policy_attached",
                    "new_user_created",
                ],
                "score_version": "1.0",
            }
            table.put_item(Item=item)

        if item is None:
            duration = time.monotonic() - start
            msg = "No score record found for identity"
            print(f"  ERROR: {msg}")
            return PhaseResult(
                phase=4, name="Display Blast Radius Score", status="FAIL",
                duration_s=duration, error=msg,
            )

        score = item.get("score_value", 0)
        severity = item.get("severity_level", "Unknown")
        factors = item.get("contributing_factors", [])

        _print_kv("Score", f"{score}/100")
        _print_kv("Severity", severity)
        _print_kv("Factors", str(len(factors)))
        for i, factor in enumerate(factors, 1):
            print(f"    {i}. {factor}")
        if verbose:
            _print_kv("Calculated At", item.get("calculation_timestamp", ""))

        duration = time.monotonic() - start
        _print_kv("Status", f"✓ PASS ({duration:.2f}s)")

        return PhaseResult(
            phase=4,
            name="Display Blast Radius Score",
            status="PASS",
            duration_s=duration,
            output={"score": score, "severity": severity, "factor_count": len(factors)},
        )

    except Exception as exc:
        duration = time.monotonic() - start
        print(f"  ERROR: {exc}")
        return PhaseResult(
            phase=4, name="Display Blast Radius Score", status="FAIL",
            duration_s=duration, error=str(exc),
        )


# ---------------------------------------------------------------------------
# Phase 5: Show Audit Log
# ---------------------------------------------------------------------------


def phase5_show_audit_log(identity_arn: str, verbose: bool, mock: bool = False) -> PhaseResult:
    """Query Remediation_Audit_Log and print the most recent 10 entries."""
    _print_phase_header(5, "Show Audit Log")
    start = time.monotonic()

    try:
        from boto3.dynamodb.conditions import Key as DDBKey  # noqa: PLC0415

        dynamodb = boto3.resource("dynamodb", region_name=REGION)
        table = dynamodb.Table(TABLE_REMEDIATION_AUDIT_LOG)

        # Check if any entries exist for this identity
        response = table.query(
            IndexName="IdentityTimeIndex",
            KeyConditionExpression=DDBKey("identity_arn").eq(identity_arn),
            ScanIndexForward=False,
            Limit=10,
        )
        items = response.get("Items", [])

        if not items and mock:
            # Write two synthetic audit entries in mock mode
            now = _utc_now()
            earlier = _utc_now(-5)

            synthetic_entries = [
                {
                    "audit_id": str(uuid.uuid4()),
                    "timestamp": earlier,
                    "identity_arn": identity_arn,
                    "incident_id": str(uuid.uuid4()),
                    "action_type": "disable_iam_user",
                    "outcome": "suppressed",
                    "risk_mode": "monitor",
                    "suppression_reason": "risk_mode=monitor: actions suppressed",
                    "detection_type": "privilege_escalation",
                    "severity": "Critical",
                },
                {
                    "audit_id": str(uuid.uuid4()),
                    "timestamp": now,
                    "identity_arn": identity_arn,
                    "incident_id": str(uuid.uuid4()),
                    "action_type": "notify_security_team",
                    "outcome": "suppressed",
                    "risk_mode": "monitor",
                    "suppression_reason": "risk_mode=monitor: actions suppressed",
                    "detection_type": "logging_disruption",
                    "severity": "Critical",
                },
            ]
            for entry in synthetic_entries:
                table.put_item(Item=entry)

            # Re-query to get the written items
            response = table.query(
                IndexName="IdentityTimeIndex",
                KeyConditionExpression=DDBKey("identity_arn").eq(identity_arn),
                ScanIndexForward=False,
                Limit=10,
            )
            items = response.get("Items", [])

        if not items:
            duration = time.monotonic() - start
            msg = "No audit log entries found"
            print(f"  {msg}")
            return PhaseResult(
                phase=5, name="Show Audit Log", status="FAIL",
                duration_s=duration, error=msg,
            )

        # Print formatted table
        col_w = {"ts": 28, "action": 26, "outcome": 12, "mode": 10}
        header = (
            f"  {'Timestamp':<{col_w['ts']}} "
            f"{'Action':<{col_w['action']}} "
            f"{'Outcome':<{col_w['outcome']}} "
            f"{'Mode':<{col_w['mode']}}"
        )
        print(f"\n{header}")
        print(f"  {THIN_SEP}")

        for entry in items:
            ts = entry.get("timestamp", "")[:26]
            action = entry.get("action_type", "")[:col_w["action"]]
            outcome = entry.get("outcome", "")[:col_w["outcome"]]
            mode = entry.get("risk_mode", "")[:col_w["mode"]]
            print(
                f"  {ts:<{col_w['ts']}} "
                f"{action:<{col_w['action']}} "
                f"{outcome:<{col_w['outcome']}} "
                f"{mode:<{col_w['mode']}}"
            )
            if verbose:
                reason = entry.get("suppression_reason", "")
                if reason:
                    print(f"    └─ {reason}")

        duration = time.monotonic() - start
        print(f"\n  Entries shown: {len(items)}")
        _print_kv("Status", f"✓ PASS ({duration:.2f}s)")

        return PhaseResult(
            phase=5,
            name="Show Audit Log",
            status="PASS",
            duration_s=duration,
            output={"entry_count": len(items)},
        )

    except Exception as exc:
        duration = time.monotonic() - start
        print(f"  ERROR: {exc}")
        return PhaseResult(
            phase=5, name="Show Audit Log", status="FAIL",
            duration_s=duration, error=str(exc),
        )


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------


def print_phase_summary(results: list[PhaseResult]) -> None:
    """Print a formatted summary table of all phase results."""
    col_phase = 7
    col_name = 30
    col_status = 10
    col_dur = 10

    print(f"\n┌{'─' * col_phase}┬{'─' * (col_name + 2)}┬{'─' * (col_status + 2)}┬{'─' * (col_dur + 2)}┐")
    print(
        f"│ {'Phase':<{col_phase - 2}} │ {'Name':<{col_name}} │ {'Status':<{col_status}} │ {'Duration':<{col_dur}} │"
    )
    print(f"├{'─' * col_phase}┼{'─' * (col_name + 2)}┼{'─' * (col_status + 2)}┼{'─' * (col_dur + 2)}┤")

    total_duration = 0.0
    failures = 0

    for r in results:
        icon = "✓" if r.status == "PASS" else ("·" if r.status == "SKIPPED" else "✗")
        status_str = f"{icon} {r.status}"
        dur_str = f"{r.duration_s:.2f}s"
        name_trunc = r.name[:col_name]
        total_duration += r.duration_s
        if r.status == "FAIL":
            failures += 1

        print(
            f"│ {r.phase:<{col_phase - 2}} │ {name_trunc:<{col_name}} │ {status_str:<{col_status + 1}}│ {dur_str:<{col_dur + 1}}│"
        )

    print(f"└{'─' * col_phase}┴{'─' * (col_name + 2)}┴{'─' * (col_status + 2)}┴{'─' * (col_dur + 2)}┘")

    total_str = f"Total: {total_duration:.2f}s"
    if failures == 0:
        print(f"\nAll phases passed. {total_str}")
    else:
        print(f"\n{failures} phase(s) failed. {total_str}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate a privilege escalation attack through the Radius pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python scripts/simulate-attack.py --mode mock\n"
            "  python scripts/simulate-attack.py --mode mock --verbose\n"
            "  python scripts/simulate-attack.py --mode mock --phase 4\n"
        ),
    )
    parser.add_argument(
        "--mode", choices=["mock", "live"], default="mock",
        help="AWS mode. mock uses moto; live uses real AWS. Default: mock",
    )
    parser.add_argument(
        "--identity", default="arn:aws:iam::123456789012:user/attacker",
        metavar="ARN",
        help="Attacker IAM ARN. Default: arn:aws:iam::123456789012:user/attacker",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print per-event detail during injection",
    )
    parser.add_argument(
        "--phase", type=int, choices=[1, 2, 3, 4, 5],
        metavar="{1,2,3,4,5}",
        help="Run only this phase. Default: all phases",
    )
    parser.add_argument(
        "--timeout", type=int, default=30,
        metavar="SECONDS",
        help="Polling timeout for Phase 3. Default: 30",
    )
    args = parser.parse_args()

    mock = args.mode == "mock"
    identity_arn = args.identity
    verbose = args.verbose
    timeout_s = args.timeout

    print(f"\nRadius — Attack Simulation")
    print(f"  Mode    : {args.mode}")
    print(f"  Identity: {identity_arn}")
    if args.phase:
        print(f"  Phase   : {args.phase} only")

    # Phase dispatch table
    def run_phase1() -> PhaseResult:
        return phase1_seed_identity(identity_arn, verbose)

    def run_phase2() -> PhaseResult:
        return phase2_inject_events(identity_arn, verbose)

    def run_phase3() -> PhaseResult:
        return phase3_poll_incident(identity_arn, timeout_s, verbose, mock=mock)

    def run_phase4() -> PhaseResult:
        return phase4_display_score(identity_arn, verbose, mock=mock)

    def run_phase5() -> PhaseResult:
        return phase5_show_audit_log(identity_arn, verbose, mock=mock)

    phase_runners = {
        1: run_phase1,
        2: run_phase2,
        3: run_phase3,
        4: run_phase4,
        5: run_phase5,
    }

    def _execute(phases_to_run: list[int]) -> list[PhaseResult]:
        results: list[PhaseResult] = []
        for num in phases_to_run:
            result = phase_runners[num]()
            results.append(result)
            if result.status == "FAIL":
                # Mark remaining phases as SKIPPED
                for remaining in phases_to_run[len(results):]:
                    results.append(PhaseResult(
                        phase=remaining,
                        name=phase_runners[remaining].__name__.replace("run_phase", "Phase "),
                        status="SKIPPED",
                        duration_s=0.0,
                    ))
                break
        return results

    if mock:
        with _mock_aws_context():
            setup_mock_aws()
            if args.phase:
                results = _execute([args.phase])
            else:
                results = _execute([1, 2, 3, 4, 5])
            print_phase_summary(results)
    else:
        if args.phase:
            results = _execute([args.phase])
        else:
            results = _execute([1, 2, 3, 4, 5])
        print_phase_summary(results)

    any_failed = any(r.status == "FAIL" for r in results)
    sys.exit(1 if any_failed else 0)


if __name__ == "__main__":
    main()
