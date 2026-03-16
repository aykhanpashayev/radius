#!/usr/bin/env python3
"""seed-dev-data.py — Populate DynamoDB tables with test data for the dev environment.

Usage:
    python scripts/seed-dev-data.py --env dev [--region us-east-1] [--prefix radius]

Only supports the dev environment in Phase 2.
"""

import argparse
import sys
import uuid
from datetime import datetime, timezone, timedelta

import boto3
from botocore.exceptions import ClientError

SUPPORTED_ENVS = {"dev"}


def utc_now(offset_hours: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(hours=offset_hours)).isoformat(timespec="microseconds")


def put(table, item: dict) -> None:
    try:
        table.put_item(Item=item)
    except ClientError as exc:
        print(f"  ERROR writing to {table.name}: {exc}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

def seed_identity_profiles(dynamodb, prefix: str) -> None:
    table = dynamodb.Table(f"{prefix}-identity-profile")
    print(f"--> Seeding {table.name}...")
    identities = [
        {
            "identity_arn": "arn:aws:iam::123456789012:user/admin-user",
            "identity_type": "IAMUser",
            "account_id": "123456789012",
            "last_activity_timestamp": utc_now(-1),
            "status": "active",
            "tags": {"Department": "Security", "Team": "Platform"},
        },
        {
            "identity_arn": "arn:aws:iam::123456789012:user/dev-user",
            "identity_type": "IAMUser",
            "account_id": "123456789012",
            "last_activity_timestamp": utc_now(-2),
            "status": "active",
            "tags": {"Department": "Engineering"},
        },
        {
            "identity_arn": "arn:aws:iam::123456789012:role/deploy-role",
            "identity_type": "AssumedRole",
            "account_id": "123456789012",
            "last_activity_timestamp": utc_now(-3),
            "status": "active",
            "tags": {},
        },
        {
            "identity_arn": "arn:aws:iam::123456789012:user/old-service-account",
            "identity_type": "IAMUser",
            "account_id": "123456789012",
            "last_activity_timestamp": utc_now(-48),
            "status": "inactive",
            "tags": {},
        },
    ]
    for item in identities:
        put(table, item)
    print(f"   Wrote {len(identities)} identity profiles")


def seed_blast_radius_scores(dynamodb, prefix: str) -> None:
    table = dynamodb.Table(f"{prefix}-blast-radius-score")
    print(f"--> Seeding {table.name}...")
    scores = [
        {
            "identity_arn": "arn:aws:iam::123456789012:user/admin-user",
            "score_value": 72,
            "severity_level": "Very High",
            "calculation_timestamp": utc_now(-1),
            "contributing_factors": ["cross_account_access", "admin_policy_attached"],
        },
        {
            "identity_arn": "arn:aws:iam::123456789012:user/dev-user",
            "score_value": 35,
            "severity_level": "Moderate",
            "calculation_timestamp": utc_now(-2),
            "contributing_factors": ["unusual_access_time"],
        },
        {
            "identity_arn": "arn:aws:iam::123456789012:role/deploy-role",
            "score_value": 50,
            "severity_level": "High",
            "calculation_timestamp": utc_now(-3),
            "contributing_factors": ["instance_profile_attached"],
        },
    ]
    for item in scores:
        put(table, item)
    print(f"   Wrote {len(scores)} blast radius scores")


def seed_incidents(dynamodb, prefix: str) -> list[str]:
    table = dynamodb.Table(f"{prefix}-incident")
    print(f"--> Seeding {table.name}...")
    incident_ids = []
    incidents = [
        {
            "incident_id": str(uuid.uuid4()),
            "identity_arn": "arn:aws:iam::123456789012:user/admin-user",
            "detection_type": "cross_account_privilege_escalation",
            "severity": "Critical",
            "confidence": 90,
            "status": "open",
            "creation_timestamp": utc_now(-2),
            "update_timestamp": utc_now(-2),
            "related_event_ids": ["f1a2b3c4-9001-9001-9001-000000009001"],
            "status_history": [{"status": "open", "timestamp": utc_now(-2)}],
            "notes": "",
            "assigned_to": "",
        },
        {
            "incident_id": str(uuid.uuid4()),
            "identity_arn": "arn:aws:iam::123456789012:user/dev-user",
            "detection_type": "unusual_access_time",
            "severity": "High",
            "confidence": 75,
            "status": "investigating",
            "creation_timestamp": utc_now(-5),
            "update_timestamp": utc_now(-1),
            "related_event_ids": ["f1a2b3c4-9001-9001-9001-000000009001"],
            "status_history": [
                {"status": "open", "timestamp": utc_now(-5)},
                {"status": "investigating", "timestamp": utc_now(-1)},
            ],
            "notes": "Reviewing VPN logs",
            "assigned_to": "security-analyst",
        },
        {
            "incident_id": str(uuid.uuid4()),
            "identity_arn": "arn:aws:iam::123456789012:user/admin-user",
            "detection_type": "admin_policy_self_attach",
            "severity": "Very High",
            "confidence": 95,
            "status": "resolved",
            "creation_timestamp": utc_now(-24),
            "update_timestamp": utc_now(-12),
            "related_event_ids": ["e1f2a3b4-0002-0002-0002-000000000002"],
            "status_history": [
                {"status": "open", "timestamp": utc_now(-24)},
                {"status": "investigating", "timestamp": utc_now(-20)},
                {"status": "resolved", "timestamp": utc_now(-12)},
            ],
            "notes": "Confirmed legitimate change request",
            "assigned_to": "security-lead",
        },
    ]
    for item in incidents:
        put(table, item)
        incident_ids.append(item["incident_id"])
    print(f"   Wrote {len(incidents)} incidents")
    return incident_ids


def seed_trust_relationships(dynamodb, prefix: str) -> None:
    table = dynamodb.Table(f"{prefix}-trust-relationship")
    print(f"--> Seeding {table.name}...")
    relationships = [
        {
            "source_arn": "arn:aws:iam::123456789012:user/admin-user",
            "target_arn": "arn:aws:iam::987654321098:role/OrganizationAccountAccessRole",
            "relationship_type": "AssumeRole",
            "target_account_id": "987654321098",
            "discovery_timestamp": utc_now(-2),
            "event_count": 1,
        },
        {
            "source_arn": "arn:aws:iam::123456789012:user/admin-user",
            "target_arn": "arn:aws:iam::987654321098:role/cross-account-admin",
            "relationship_type": "AssumeRole",
            "target_account_id": "987654321098",
            "discovery_timestamp": utc_now(-5),
            "event_count": 3,
        },
        {
            "source_arn": "arn:aws:iam::123456789012:role/deploy-role",
            "target_arn": "arn:aws:iam::123456789012:instance-profile/app-instance-profile",
            "relationship_type": "InstanceProfile",
            "target_account_id": "123456789012",
            "discovery_timestamp": utc_now(-10),
            "event_count": 1,
        },
    ]
    for item in relationships:
        put(table, item)
    print(f"   Wrote {len(relationships)} trust relationships")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Seed DynamoDB tables with test data")
    parser.add_argument("--env", required=True, choices=list(SUPPORTED_ENVS),
                        help="Target environment (only 'dev' supported in Phase 2)")
    parser.add_argument("--region", default="us-east-1")
    parser.add_argument("--prefix", default="radius",
                        help="Resource naming prefix (default: radius)")
    args = parser.parse_args()

    name_prefix = f"{args.prefix}-{args.env}"
    print(f"==> Seeding dev data [prefix={name_prefix}, region={args.region}]")

    dynamodb = boto3.resource("dynamodb", region_name=args.region)

    try:
        seed_identity_profiles(dynamodb, name_prefix)
        seed_blast_radius_scores(dynamodb, name_prefix)
        seed_incidents(dynamodb, name_prefix)
        seed_trust_relationships(dynamodb, name_prefix)
    except ClientError as exc:
        print(f"\nFATAL: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\n==> Seeding complete.")


if __name__ == "__main__":
    main()
